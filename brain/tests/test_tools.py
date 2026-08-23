"""Tests for Gemini tool use — the gather phase and its executors.

Two properties matter more than the happy path, and both are about failure:

1. Tool use is optional. Every failure must produce EMPTY and let the diagnosis
   proceed, because a diagnosis without gathered context is exactly the
   diagnosis this service produced before tools existed. A gather step that can
   take the diagnosis down with it is worse than no gather step.

2. Web citations come from grounding metadata, never from model prose. This
   project has already shipped one uncheckable citation to farmers
   (see test_rag.py); search grounding is a second chance to do it.
"""

import asyncio
import unittest
from types import SimpleNamespace
from unittest import mock

from brain.services import grounding
from brain.services.grounding import EMPTY, GatheredContext, _extract_web_sources
from brain.services.tools import TOOL_SCHEMAS, execute_tool


def run(coro):
    return asyncio.run(coro)


class ToolExecutorTest(unittest.TestCase):
    def test_unknown_tool_returns_error_not_raise(self):
        result = run(execute_tool("drop_table", {}))
        self.assertIn("error", result)

    def test_failing_tool_returns_error_not_raise(self):
        with mock.patch.dict(
            "brain.services.tools.EXECUTORS",
            {"boom": mock.AsyncMock(side_effect=RuntimeError("ground is down"))},
        ):
            result = run(execute_tool("boom", {}))
        self.assertIn("error", result)
        self.assertIn("ground is down", result["error"])

    def test_bad_arguments_are_reported_back_to_the_model(self):
        async def needs_lat(lat: float):
            return {"ok": lat}

        with mock.patch.dict("brain.services.tools.EXECUTORS", {"needs_lat": needs_lat}):
            result = run(execute_tool("needs_lat", {"latitude": 1.0}))
        self.assertIn("error", result)

    def test_timeout_is_reported_as_unavailable(self):
        async def never():
            await asyncio.sleep(10)

        with mock.patch.dict("brain.services.tools.EXECUTORS", {"never": never}), \
             mock.patch("brain.services.tools.TOOL_TIMEOUT_S", 0.01):
            result = run(execute_tool("never", {}))
        self.assertIn("error", result)
        self.assertIn("timed out", result["error"])

    def test_retrieval_tool_preserves_provenance(self):
        """A built-in note must stay uncitable when it reaches the model."""
        builtin = [{"content": "text", "source": None, "provenance": "builtin"}]
        with mock.patch(
            "brain.services.tools.rag_service.retrieve_context", return_value=builtin
        ):
            result = run(execute_tool("retrieve_icar_docs", {"crop": "Tomato", "query": "spots"}))
        self.assertFalse(result["citable"])
        self.assertIsNone(result["documents"][0]["source"])

    def test_retrieval_tool_marks_corpus_chunks_citable(self):
        corpus = [{"content": "text", "source": "icar_tomato.pdf", "provenance": "corpus"}]
        with mock.patch(
            "brain.services.tools.rag_service.retrieve_context", return_value=corpus
        ):
            result = run(execute_tool("retrieve_icar_docs", {"crop": "Tomato", "query": "spots"}))
        self.assertTrue(result["citable"])
        self.assertEqual(result["documents"][0]["source"], "icar_tomato.pdf")

    def test_every_declared_tool_has_an_executor(self):
        from brain.services.tools import EXECUTORS

        for schema in TOOL_SCHEMAS:
            self.assertIn(schema["name"], EXECUTORS)

    def test_dosage_rule_is_stated_on_the_retrieval_tool(self):
        """The model reads these descriptions; the dosage rule has to be in one."""
        retrieval = next(s for s in TOOL_SCHEMAS if s["name"] == "retrieve_icar_docs")
        self.assertIn("dosage", retrieval["description"].lower())


class GroundingCitationTest(unittest.TestCase):
    def _response(self, chunks):
        return SimpleNamespace(
            candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(grounding_chunks=chunks))]
        )

    def test_citations_come_from_grounding_metadata(self):
        chunk = SimpleNamespace(web=SimpleNamespace(uri="https://icar.org.in/x", title="ICAR"))
        sources = _extract_web_sources(self._response([chunk]))
        self.assertEqual(sources, [{"uri": "https://icar.org.in/x", "title": "ICAR"}])

    def test_missing_metadata_yields_no_citations(self):
        self.assertEqual(_extract_web_sources(SimpleNamespace(candidates=[])), [])
        self.assertEqual(
            _extract_web_sources(SimpleNamespace(candidates=[SimpleNamespace()])), []
        )

    def test_malformed_response_does_not_raise(self):
        self.assertEqual(_extract_web_sources(object()), [])

    def test_source_urls_are_deduplicated_in_order(self):
        gathered = GatheredContext(
            web_sources=[
                {"uri": "https://b.example", "title": "b"},
                {"uri": "https://a.example", "title": "a"},
                {"uri": "https://b.example", "title": "b again"},
                {"uri": "", "title": "empty"},
            ]
        )
        self.assertEqual(
            gathered.source_urls(), ["https://b.example", "https://a.example"]
        )


class FakeTypes:
    """Enough of google.genai.types to drive _run_gather without the SDK."""

    class GenerateContentConfig:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class Content:
        def __init__(self, role=None, parts=None):
            self.role, self.parts = role, parts

    class Part:
        @staticmethod
        def from_function_response(name, response):
            return {"name": name, "response": response}

    class Tool:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class GoogleSearch:
        pass


def _reply(text=None, calls=(), chunks=()):
    """A fake GenerateContentResponse."""
    content = SimpleNamespace(role="model", parts=[])
    return SimpleNamespace(
        text=text,
        function_calls=[SimpleNamespace(name=n, args=a) for n, a in calls],
        candidates=[SimpleNamespace(
            content=content,
            grounding_metadata=SimpleNamespace(grounding_chunks=list(chunks)),
        )],
    )


def _web_chunk(uri, title="t"):
    return SimpleNamespace(web=SimpleNamespace(uri=uri, title=title))


class GatherLoopTest(unittest.TestCase):
    """The tool-call loop: rounds, laddering, and what it carries out."""

    def setUp(self):
        self.types = FakeTypes
        patcher = mock.patch(
            "brain.services.grounding._build_tool_configs",
            return_value=[("search+functions", ["sf"]), ("functions", ["f"]), ("search", ["s"])],
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _client(self, replies):
        """A fake key pool that plays `replies` in order, raising any exception."""

        class FakePool:
            def __init__(self):
                self.queue = list(replies)
                self.calls = 0

            async def generate(self, *, model, contents, config):
                self.calls += 1
                item = self.queue.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

        return FakePool()

    def test_returns_notes_when_the_model_stops_calling_tools(self):
        client = self._client([_reply(text="  blight is being reported locally  ")])
        result = run(grounding._run_gather(client, self.types, []))
        self.assertEqual(result.notes, "blight is being reported locally")
        self.assertEqual(result.tools_called, [])

    def test_function_calls_are_executed_and_fed_back(self):
        client = self._client([
            _reply(calls=[("retrieve_icar_docs", {"crop": "Onion", "query": "purple blotch"})]),
            _reply(text="ICAR describes purple blotch"),
        ])
        contents = []
        with mock.patch(
            "brain.services.grounding.execute_tool",
            new=mock.AsyncMock(return_value={"documents": []}),
        ) as ex:
            result = run(grounding._run_gather(client, self.types, contents))

        ex.assert_awaited_once_with("retrieve_icar_docs", {"crop": "Onion", "query": "purple blotch"})
        self.assertEqual(result.tools_called, ["retrieve_icar_docs"])
        self.assertEqual(result.notes, "ICAR describes purple blotch")
        # The model turn and our function-response turn both entered the history.
        self.assertEqual(len(contents), 2)

    def test_parallel_calls_in_one_round_are_all_serviced(self):
        client = self._client([
            _reply(calls=[("retrieve_icar_docs", {}), ("get_nearby_outbreaks", {})]),
            _reply(text="done"),
        ])
        with mock.patch(
            "brain.services.grounding.execute_tool", new=mock.AsyncMock(return_value={})
        ) as ex:
            result = run(grounding._run_gather(client, self.types, []))
        self.assertEqual(ex.await_count, 2)
        self.assertEqual(result.tools_called, ["retrieve_icar_docs", "get_nearby_outbreaks"])

    def test_round_ceiling_stops_a_runaway_loop(self):
        """A model that never stops calling tools must not run forever."""
        client = self._client([_reply(calls=[("retrieve_icar_docs", {})])] * 20)
        with mock.patch(
            "brain.services.grounding.execute_tool", new=mock.AsyncMock(return_value={})
        ):
            result = run(grounding._run_gather(client, self.types, []))
        self.assertEqual(client.calls, grounding.MAX_TOOL_ROUNDS)
        self.assertTrue(result.is_empty)

    def test_rejected_tool_combination_steps_down_the_ladder(self):
        """Not every model build accepts google_search beside function declarations."""
        client = self._client([
            ValueError("tools + search unsupported"),
            _reply(text="gathered anyway"),
        ])
        result = run(grounding._run_gather(client, self.types, []))
        self.assertEqual(result.notes, "gathered anyway")

    def test_stepping_down_does_not_consume_a_tool_round(self):
        """A rejected combination never reached the model, so it is not a turn."""
        replies = [ValueError("no"), ValueError("no")]
        replies += [_reply(calls=[("retrieve_icar_docs", {})])] * 20
        client = self._client(replies)
        with mock.patch(
            "brain.services.grounding.execute_tool", new=mock.AsyncMock(return_value={})
        ):
            run(grounding._run_gather(client, self.types, []))
        # 2 rejections + MAX_TOOL_ROUNDS real turns.
        self.assertEqual(
            client.calls, 2 + grounding.MAX_TOOL_ROUNDS
        )

    def test_exhausted_ladder_propagates(self):
        """Out of fallbacks, the error must reach gather_context's soft handler."""
        client = self._client([ValueError("a"), ValueError("b"), ValueError("c")])
        with self.assertRaises(ValueError):
            run(grounding._run_gather(client, self.types, []))

    def test_citations_accumulate_across_rounds(self):
        client = self._client([
            _reply(calls=[("retrieve_icar_docs", {})], chunks=[_web_chunk("https://a.example")]),
            _reply(text="done", chunks=[_web_chunk("https://b.example")]),
        ])
        with mock.patch(
            "brain.services.grounding.execute_tool", new=mock.AsyncMock(return_value={})
        ):
            result = run(grounding._run_gather(client, self.types, []))
        self.assertEqual(result.source_urls(), ["https://a.example", "https://b.example"])

    def test_a_failing_tool_does_not_abort_the_gather(self):
        client = self._client([
            _reply(calls=[("get_nearby_outbreaks", {})]),
            _reply(text="outbreak data was unavailable"),
        ])
        with mock.patch(
            "brain.services.grounding.execute_tool",
            new=mock.AsyncMock(return_value={"error": "ground unavailable"}),
        ):
            result = run(grounding._run_gather(client, self.types, []))
        self.assertEqual(result.notes, "outbreak data was unavailable")


class GatherFailsSoftTest(unittest.TestCase):
    """The gather phase must never be able to break a diagnosis."""

    def setUp(self):
        self.passport = mock.Mock()
        self.passport.model_dump.return_value = {"district": "Nashik"}

    def test_disabled_returns_empty_without_calling_gemini(self):
        client = mock.Mock()
        with mock.patch.object(grounding, "ENABLED", False):
            result = run(grounding.gather_context(client, self.passport))
        self.assertIs(result, EMPTY)
        client.models.generate_content.assert_not_called()

    def test_missing_client_returns_empty(self):
        with mock.patch.object(grounding, "ENABLED", True):
            self.assertIs(run(grounding.gather_context(None, self.passport)), EMPTY)

    def test_sdk_absent_returns_empty(self):
        """No google-genai installed must not raise into the diagnosis."""
        with mock.patch.object(grounding, "ENABLED", True), \
             mock.patch.dict("sys.modules", {"google.genai": None}):
            result = run(grounding.gather_context(mock.Mock(), self.passport))
        self.assertIs(result, EMPTY)

    def test_exception_inside_gather_returns_empty(self):
        with mock.patch.object(grounding, "ENABLED", True), \
             mock.patch.object(grounding, "_run_gather", side_effect=RuntimeError("api on fire")), \
             mock.patch.dict("sys.modules", {"google.genai": mock.Mock()}):
            result = run(grounding.gather_context(mock.Mock(), self.passport))
        self.assertIs(result, EMPTY)

    def test_budget_overrun_returns_empty(self):
        async def slow(*_a, **_k):
            await asyncio.sleep(10)

        with mock.patch.object(grounding, "ENABLED", True), \
             mock.patch.object(grounding, "GATHER_BUDGET_S", 0.01), \
             mock.patch.object(grounding, "_run_gather", slow), \
             mock.patch.dict("sys.modules", {"google.genai": mock.Mock()}):
            result = run(grounding.gather_context(mock.Mock(), self.passport))
        self.assertIs(result, EMPTY)

    def test_empty_context_is_falsy_for_the_caller(self):
        self.assertTrue(EMPTY.is_empty)
        self.assertEqual(EMPTY.source_urls(), [])
        self.assertFalse(GatheredContext(notes="found something").is_empty)


if __name__ == "__main__":
    unittest.main()
