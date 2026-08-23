"""Multi-key fail-over.

Two defects this guards against:

1. Three keys in .env and none in use. The service read only GEMINI_API_KEY, so
   GEMINI_API_KEY_1/2/3 were invisible and every diagnosis escalated while the
   log said "missing API key".
2. Rotating on the wrong errors. Gemini's free tier meters per key AND per
   model, so 429 is worth another key — but a 404 (model retired) or 403 (bad
   key) is not, and retrying those burns every remaining key to reach the same
   failure.
"""

import asyncio
import os
import unittest
from unittest import mock

from brain.services import genai_pool as pool_module
from brain.services.genai_pool import GeminiPool, discover_keys


def run(coro):
    return asyncio.run(coro)


class FakeClient:
    """One key's client. `script` is replayed per call."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    class _Models:
        def __init__(self, outer):
            self.outer = outer

        def generate_content(self, *, model, contents, config):
            self.outer.calls += 1
            item = self.outer.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    @property
    def models(self):
        return self._Models(self)


def _pool(*scripts) -> GeminiPool:
    import itertools
    p = GeminiPool.__new__(GeminiPool)
    p._clients = [FakeClient(s) for s in scripts]
    p._labels = [f"key{i+1}(...zzzz)" for i in range(len(scripts))]
    p._turn = itertools.count()
    p._cooldown = {}
    return p


def quota():
    return RuntimeError("429 RESOURCE_EXHAUSTED. You exceeded your current quota")


class KeyDiscoveryTest(unittest.TestCase):
    def test_finds_the_suffixed_keys(self):
        env = {"GEMINI_API_KEY_1": "a", "GEMINI_API_KEY_2": "b", "GEMINI_API_KEY_3": "c"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(discover_keys(), ["a", "b", "c"])

    def test_unsuffixed_key_comes_first(self):
        env = {"GEMINI_API_KEY": "plain", "GEMINI_API_KEY_1": "one"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(discover_keys(), ["plain", "one"])

    def test_duplicates_and_blanks_are_dropped(self):
        env = {"GEMINI_API_KEY": "same", "GEMINI_API_KEY_1": "same", "GEMINI_API_KEY_2": "  "}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(discover_keys(), ["same"])

    def test_no_keys_is_empty_not_an_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(discover_keys(), [])


class RotationTest(unittest.TestCase):
    def test_exhausted_key_falls_over_to_the_next(self):
        good = mock.Mock(text="ok")
        p = _pool([quota()], [good])
        result = run(p.generate(model="m", contents=["x"], config=None))
        self.assertIs(result, good)
        self.assertEqual(p._clients[0].calls, 1)
        self.assertEqual(p._clients[1].calls, 1)

    def test_a_cooling_key_is_not_retried_on_every_request(self):
        """A spent key must sit out, not be re-probed by each new farmer."""
        p = _pool([quota(), quota()], [mock.Mock(text="a"), mock.Mock(text="b")])
        run(p.generate(model="m", contents=["x"], config=None))
        run(p.generate(model="m", contents=["x"], config=None))
        # Key 1 was tried once and then skipped, not tried again.
        self.assertEqual(p._clients[0].calls, 1)
        self.assertEqual(p._clients[1].calls, 2)

    def test_cooldown_is_per_key_and_model_not_per_key(self):
        """Measured reality: a key can be spent for one model and fine on another."""
        p = _pool([quota(), mock.Mock(text="other-model-ok")], [mock.Mock(text="b")])
        run(p.generate(model="3.6", contents=["x"], config=None))   # key1 fails, key2 serves
        self.assertTrue(p._is_cooling(0, "3.6"))
        self.assertFalse(p._is_cooling(0, "3.5"), "a different model must not be blocked")

    def test_success_clears_a_stale_cooldown(self):
        p = _pool([mock.Mock(text="ok")], [mock.Mock(text="b")])
        p._cooldown[(0, "m")] = __import__("time").monotonic() + 999
        run(p.generate(model="m", contents=["x"], config=None))
        # Whichever key served, a served key must not remain marked as cooling.
        self.assertTrue(all(not p._is_cooling(i, "m") for i in range(2)
                            if p._clients[i].calls > 0))

    def test_every_key_cooling_still_attempts_rather_than_giving_up(self):
        """The cooldown is a guess; never refuse to make a request because of it."""
        p = _pool([mock.Mock(text="ok")], [mock.Mock(text="b")])
        now = __import__("time").monotonic()
        p._cooldown = {(0, "m"): now + 999, (1, "m"): now + 999}
        self.assertIsNotNone(run(p.generate(model="m", contents=["x"], config=None)))

    def test_all_keys_exhausted_raises_the_last_error(self):
        p = _pool([quota()], [quota()])
        with self.assertRaises(RuntimeError) as caught:
            run(p.generate(model="m", contents=["x"], config=None))
        self.assertIn("429", str(caught.exception))

    def test_transient_overload_also_rotates(self):
        good = mock.Mock(text="ok")
        p = _pool([RuntimeError("503 UNAVAILABLE model is overloaded")], [good])
        self.assertIs(run(p.generate(model="m", contents=["x"], config=None)), good)

    def test_a_retired_model_does_not_burn_every_key(self):
        """404 is the model being gone; another key cannot fix that."""
        p = _pool([RuntimeError("404 NOT_FOUND model no longer available")], [mock.Mock()])
        with self.assertRaises(RuntimeError):
            run(p.generate(model="m", contents=["x"], config=None))
        self.assertEqual(p._clients[1].calls, 0, "second key must not be tried")

    def test_a_denied_project_rotates_to_another_key(self):
        """403 is key-specific: the other keys belong to other projects.

        Grouping it with 404/400 meant one denied key in four failed one
        diagnosis in four under round-robin.
        """
        good = mock.Mock(text="ok")
        p = _pool([RuntimeError("403 PERMISSION_DENIED. Your project has been denied access")], [good])
        self.assertIs(run(p.generate(model="m", contents=["x"], config=None)), good)

    def test_a_denied_key_is_benched_for_longer_than_a_quota_blip(self):
        """A denied project needs a human; re-probing it every minute is noise."""
        import time as _t
        p = _pool([RuntimeError("403 PERMISSION_DENIED")], [mock.Mock(text="ok")])
        run(p.generate(model="m", contents=["x"], config=None))
        remaining = p._cooldown[(0, "m")] - _t.monotonic()
        self.assertGreater(remaining, pool_module.COOLDOWN_S)

    def test_a_bad_request_does_not_rotate(self):
        p = _pool([RuntimeError("400 INVALID_ARGUMENT")], [mock.Mock()])
        with self.assertRaises(RuntimeError):
            run(p.generate(model="m", contents=["x"], config=None))
        self.assertEqual(p._clients[1].calls, 0)

    def test_no_keys_raises_rather_than_hanging(self):
        p = _pool()
        with self.assertRaises(RuntimeError):
            run(p.generate(model="m", contents=["x"], config=None))


class SpreadTest(unittest.TestCase):
    """Round-robin, not stickiness: four farmers must not queue behind one key."""

    def test_consecutive_calls_use_different_keys(self):
        p = _pool(*[[mock.Mock(text=f"r{i}") for i in range(3)] for _ in range(4)])
        for _ in range(4):
            run(p.generate(model="m", contents=["x"], config=None))
        used = [c.calls for c in p._clients]
        self.assertEqual(used, [1, 1, 1, 1], f"load not spread evenly: {used}")

    def test_load_stays_even_over_many_calls(self):
        p = _pool(*[[mock.Mock(text="r") for _ in range(10)] for _ in range(4)])
        for _ in range(12):
            run(p.generate(model="m", contents=["x"], config=None))
        self.assertEqual([c.calls for c in p._clients], [3, 3, 3, 3])


class StatusTest(unittest.TestCase):
    def test_status_never_exposes_a_usable_key(self):
        import itertools
        p = GeminiPool.__new__(GeminiPool)
        p._clients, p._labels = [object()], ["key1(...abcd)"]
        p._turn, p._cooldown = itertools.count(), {}
        blob = repr(p.status())
        self.assertIn("key1(...abcd)", blob)
        self.assertNotIn("AIza", blob)

    def test_status_reports_the_count(self):
        p = _pool([mock.Mock()], [mock.Mock()], [mock.Mock()])
        self.assertEqual(p.status()["keys_configured"], 3)


if __name__ == "__main__":
    unittest.main()
