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
    p = GeminiPool.__new__(GeminiPool)
    p._clients = [FakeClient(s) for s in scripts]
    p._labels = [f"key{i+1}(...zzzz)" for i in range(len(scripts))]
    p._current = 0
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

    def test_the_working_key_becomes_the_starting_point(self):
        """A spent key must not be retried first on every later request."""
        p = _pool([quota(), quota()], [mock.Mock(text="a"), mock.Mock(text="b")])
        run(p.generate(model="m", contents=["x"], config=None))
        self.assertEqual(p._current, 1)
        run(p.generate(model="m", contents=["x"], config=None))
        # Key 1 was tried once, not twice.
        self.assertEqual(p._clients[0].calls, 1)
        self.assertEqual(p._clients[1].calls, 2)

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

    def test_a_bad_request_does_not_rotate(self):
        p = _pool([RuntimeError("400 INVALID_ARGUMENT")], [mock.Mock()])
        with self.assertRaises(RuntimeError):
            run(p.generate(model="m", contents=["x"], config=None))
        self.assertEqual(p._clients[1].calls, 0)

    def test_no_keys_raises_rather_than_hanging(self):
        p = _pool()
        with self.assertRaises(RuntimeError):
            run(p.generate(model="m", contents=["x"], config=None))


class StatusTest(unittest.TestCase):
    def test_status_never_exposes_a_usable_key(self):
        p = GeminiPool.__new__(GeminiPool)
        p._clients, p._labels, p._current = [object()], ["key1(...abcd)"], 0
        blob = repr(p.status())
        self.assertIn("key1(...abcd)", blob)
        self.assertNotIn("AIza", blob)

    def test_status_reports_the_count(self):
        p = _pool([mock.Mock()], [mock.Mock()], [mock.Mock()])
        self.assertEqual(p.status()["keys_configured"], 3)


if __name__ == "__main__":
    unittest.main()
