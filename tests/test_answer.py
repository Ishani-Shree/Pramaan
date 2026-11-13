"""Answering pipeline: JSON parsing, citation checks, and every abstain path."""

import json

import pytest

from app.answer import (
    ABSTAIN_TEXT,
    LLMAnswer,
    answer_question,
    check_citations,
    parse_llm_json,
    render_answer,
)
from app.ingest import ingest_corpus
from app.llm import LLMError
from tests.conftest import FakeLLM, chunk_ids_in, cite_first

GOOD = {"abstained": False, "claims": [{"text": "Port 7001.", "chunk_ids": [3]}]}


# ---------------------------------------------------------------- parsing (pure)

def test_parse_plain_json():
    parsed = parse_llm_json(json.dumps(GOOD))
    assert parsed.claims[0].chunk_ids == [3]


def test_parse_fenced_json():
    assert parse_llm_json("```json\n" + json.dumps(GOOD) + "\n```").abstained is False


@pytest.mark.parametrize("raw", [
    "Sure! Here is the answer.",                       # not JSON
    '{"answer": "port 7001"}',                         # wrong shape
    '{"abstained": "maybe", "claims": []}',            # wrong type
    '{"abstained": false, "claims": [{"text": ""}]}',  # claim missing ids, empty text
    "",
])
def test_parse_rejects_bad_replies(raw):
    with pytest.raises(ValueError):
        parse_llm_json(raw)


# ---------------------------------------------------------------- citations (pure)

def test_citations_valid():
    assert check_citations(LLMAnswer.model_validate(GOOD), {3, 4}) is None


def test_citation_to_unretrieved_chunk_is_rejected():
    reason, detail = check_citations(LLMAnswer.model_validate(GOOD), {1, 2})
    assert reason == "invalid_citation" and "[3]" in detail


def test_claim_without_citation_is_rejected():
    parsed = LLMAnswer.model_validate({"abstained": False, "claims": [{"text": "x", "chunk_ids": []}]})
    assert check_citations(parsed, {1})[0] == "uncited_claim"


def test_answer_with_no_claims_is_rejected():
    parsed = LLMAnswer.model_validate({"abstained": False, "claims": []})
    assert check_citations(parsed, {1})[0] == "uncited_claim"


def test_render_answer_dedupes_markers():
    parsed = LLMAnswer.model_validate({"abstained": False, "claims": [{"text": "A.", "chunk_ids": [2, 2, 5]}]})
    assert render_answer(parsed) == "A. [2][5]"


# ---------------------------------------------------------------- full pipeline (DB + fakes)

Q = "What is the default port of alpha?"


@pytest.fixture
def ask(conn, embedder, corpus_dir):
    ingest_corpus(conn, embedder, corpus_dir, 300, 50)

    def _ask(llm, question=Q, min_similarity=0.05):
        return answer_question(conn, embedder, llm, question, "s300_o50", 3, "hybrid", min_similarity)
    return _ask


def test_valid_answer_has_sources_from_retrieved_chunks(ask):
    llm = FakeLLM(cite_first())
    r = ask(llm)
    assert r.abstained is False and r.reason is None
    assert r.answer.startswith("Alpha listens on port 7001.")
    assert len(r.sources) == 1
    assert r.sources[0].chunk_id in r.retrieved_ids
    assert r.sources[0].source_file == "alpha.md"
    assert r.llm_calls == 1


def test_prompt_contains_only_retrieved_chunks_with_ids(ask):
    llm = FakeLLM(cite_first())
    r = ask(llm)
    assert chunk_ids_in(llm.prompts[0]) == r.retrieved_ids


def test_low_similarity_abstains_without_calling_llm(ask):
    llm = FakeLLM()  # any call would raise
    r = ask(llm, question="zebra croissant quantum")
    assert r.abstained and r.reason == "low_similarity"
    assert r.llm_calls == 0 and llm.prompts == []
    assert r.answer == ABSTAIN_TEXT


def test_threshold_is_applied(ask):
    r = ask(FakeLLM(), min_similarity=0.999)
    assert r.reason == "low_similarity"


def test_invalid_json_is_retried_once_then_succeeds(ask):
    llm = FakeLLM("not json at all", cite_first())
    r = ask(llm)
    assert r.abstained is False and r.llm_calls == 2
    assert "rejected" in llm.prompts[1]  # the retry tells the model what was wrong


def test_invalid_json_twice_abstains(ask):
    llm = FakeLLM("not json", '{"answer": 1}')
    r = ask(llm)
    assert r.abstained and r.reason == "invalid_json" and r.llm_calls == 2


def test_hallucinated_chunk_id_abstains(ask):
    llm = FakeLLM(json.dumps({"abstained": False, "claims": [{"text": "x", "chunk_ids": [999999]}]}))
    r = ask(llm)
    assert r.abstained and r.reason == "invalid_citation"
    assert r.sources == []


def test_uncited_claim_abstains(ask):
    llm = FakeLLM(json.dumps({"abstained": False, "claims": [{"text": "x", "chunk_ids": []}]}))
    assert ask(llm).reason == "uncited_claim"


def test_model_abstention_is_respected(ask):
    r = ask(FakeLLM('{"abstained": true, "claims": []}'))
    assert r.abstained and r.reason == "model_abstained"


def test_llm_outage_abstains(ask):
    r = ask(FakeLLM(LLMError("429 quota exceeded")))
    assert r.abstained and r.reason == "llm_error" and "429" in r.detail
