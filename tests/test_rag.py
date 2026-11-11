"""Unit tests for RAG generation; no network calls or vector index required."""

import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import errors

from src import rag


@pytest.fixture
def reviews():
    """Provide two representative reviews for isolated RAG tests."""
    return [
        {"review_id": "review_001", "document": "Produto não foi entregue."},
        {"review_id": "review_002", "document": "Entrega atrasada."},
    ]


@pytest.fixture
def grounded():
    """Provide a valid generated answer supported by one review."""
    return {
        "answer": "Há relatos de produto não entregue.",
        "cited_review_ids": ["review_001"],
        "insufficient_evidence": False,
        "insufficiency_reason": "nenhuma",
    }


def mock_retrieval(monkeypatch, reviews):
    """Replace semantic retrieval with a deterministic result."""
    retrieval = {"query": "Produto não entregue?", "reviews": reviews}
    mocked = Mock(return_value=retrieval)
    monkeypatch.setattr(rag, "retrieve_reviews", mocked)
    return mocked


def mock_llm(monkeypatch, *outputs):
    """Replace Gemini calls with the supplied sequence of responses."""
    responses = [SimpleNamespace(text=json.dumps(item)) if isinstance(item, dict)
                 else SimpleNamespace(text=item) for item in outputs]
    mocked = Mock(side_effect=responses)
    monkeypatch.setattr(rag, "call_llm", mocked)
    return mocked


def run_generation(**kwargs):
    """Run the RAG pipeline with inert external dependencies."""
    return rag.generate_answer(
        question="  Produto não entregue?  ",
        collection=object(),
        embedding_model=object(),
        llm_client=object(),
        llm_model="gemini-test",
        **kwargs,
    )


def test_build_context_empty():
    """Return an explicit message when no reviews are available."""
    assert rag.build_context([]) == "Nenhuma avaliação recuperada."


def test_build_context_escapes_review_tags(reviews):
    """Escape review-supplied tags without altering context delimiters."""
    reviews[0]["document"] = "<avaliacao>texto</avaliacao>"
    context = rag.build_context(reviews)
    assert '<avaliacao id="review_001">' in context
    assert "&lt;avaliacao&gt;texto&lt;/avaliacao&gt;" in context
    assert "<avaliacao>texto</avaliacao>" not in context


def test_validate_generation_accepts_grounded(reviews, grounded):
    """Accept a grounded response with a valid citation and reason."""
    assert rag.validate_generation(grounded, reviews) == grounded


def test_validate_generation_deduplicates_citations(reviews, grounded):
    """Remove repeated citations while preserving their original order."""
    grounded["cited_review_ids"] = ["review_001", "review_001", "review_002"]
    result = rag.validate_generation(grounded, reviews)
    assert result["cited_review_ids"] == ["review_001", "review_002"]


@pytest.mark.parametrize("change", [
    {"answer": "  "},
    {"cited_review_ids": "review_001"},
    {"cited_review_ids": ["unknown"]},
    {"cited_review_ids": []},
    {"insufficient_evidence": "false"},
    {"insufficiency_reason": "desconhecido"},
    {"insufficiency_reason": "fora_do_escopo"},
    {"answer": "A avaliação review_001 confirma o problema."},
])
def test_validate_generation_rejects_invalid_grounded(reviews, grounded, change):
    """Reject malformed or inconsistent grounded model responses."""
    grounded.update(change)
    with pytest.raises(ValueError):
        rag.validate_generation(grounded, reviews)


@pytest.mark.parametrize("reason", [
    "fora_do_escopo", "pergunta_vaga", "evidencia_insuficiente"
])
def test_validate_generation_accepts_abstention(reviews, grounded, reason):
    """Accept each supported reason for abstaining without citations."""
    grounded.update(cited_review_ids=[], insufficient_evidence=True,
                    insufficiency_reason=reason)
    assert rag.validate_generation(grounded, reviews)["insufficient_evidence"] is True


@pytest.mark.parametrize("change", [
    {"cited_review_ids": ["review_001"]},
    {"insufficiency_reason": "nenhuma"},
])
def test_validate_generation_rejects_invalid_abstention(reviews, grounded, change):
    """Reject abstentions that contain citations or inconsistent reasons."""
    grounded.update(cited_review_ids=[], insufficient_evidence=True,
                    insufficiency_reason="fora_do_escopo")
    grounded.update(change)
    with pytest.raises(ValueError):
        rag.validate_generation(grounded, reviews)


def test_validate_generation_rejects_non_dict(reviews):
    """Reject model responses that are not JSON objects."""
    with pytest.raises(ValueError):
        rag.validate_generation([], reviews)


def test_generate_answer_no_reviews_does_not_call_llm(monkeypatch):
    """Abstain without calling Gemini when retrieval returns no reviews."""
    mock_retrieval(monkeypatch, [])
    monkeypatch.setattr(rag, "call_llm", Mock(side_effect=AssertionError("called")))
    result = run_generation()
    assert result["status"] == "abstencao"
    assert result["insufficiency_reason"] == "evidencia_insuficiente"
    assert result["cited_review_ids"] == []


def test_generate_answer_grounded_with_one_citation_is_limited(monkeypatch, reviews, grounded):
    """Flag a one-citation answer without rejecting its evidence."""
    retrieval = mock_retrieval(monkeypatch, reviews)
    llm = mock_llm(monkeypatch, grounded)
    result = run_generation(top_k=20, min_citations=2)
    assert result["status"] == "respondida"
    assert result["insufficient_evidence"] is False
    assert result["limited_evidence"] is True
    assert result["cited_review_ids"] == ["review_001"]
    assert result["error"] is None
    assert retrieval.call_args.kwargs["top_k"] == 20
    assert "review_001" in llm.call_args.args[2]


def test_generate_answer_two_citations_not_limited(monkeypatch, reviews, grounded):
    """Do not flag an answer meeting the minimum citation count."""
    mock_retrieval(monkeypatch, reviews)
    grounded["cited_review_ids"] = ["review_001", "review_002"]
    mock_llm(monkeypatch, grounded)
    assert run_generation()["limited_evidence"] is False


def test_generate_answer_abstains(monkeypatch, reviews, grounded):
    """Preserve the abstention status and its specific reason."""
    mock_retrieval(monkeypatch, reviews)
    grounded.update(answer="Não há evidências.", cited_review_ids=[],
                    insufficient_evidence=True, insufficiency_reason="fora_do_escopo")
    mock_llm(monkeypatch, grounded)
    result = run_generation()
    assert result["status"] == "abstencao"
    assert result["insufficiency_reason"] == "fora_do_escopo"
    assert result["limited_evidence"] is False


def test_generate_answer_retries_invalid_model_output(monkeypatch, reviews, grounded):
    """Retry generation after invalid JSON and accept a valid retry."""
    mock_retrieval(monkeypatch, reviews)
    llm = mock_llm(monkeypatch, "not json", grounded)
    result = run_generation()
    assert result["status"] == "respondida"
    assert llm.call_count == 2
    assert "resposta anterior foi rejeitada" in llm.call_args.args[2]


def test_generate_answer_invalid_twice_is_technical_error(monkeypatch, reviews):
    """Report repeated invalid model output as a technical failure."""
    mock_retrieval(monkeypatch, reviews)
    mock_llm(monkeypatch, "not json", "not json")
    result = run_generation()
    assert result["status"] == "erro"
    assert result["insufficient_evidence"] is None
    assert result["insufficiency_reason"] == "erro_geracao"
    assert result["error"]
    assert result["cited_review_ids"] == []


def test_generate_answer_api_error_is_technical_error(monkeypatch, reviews):
    """Classify an API failure as an error rather than an abstention."""
    mock_retrieval(monkeypatch, reviews)
    api_error = errors.ClientError(429, {"error": {"message": "Quota exceeded"}})
    monkeypatch.setattr(rag, "call_llm", Mock(side_effect=api_error))
    result = run_generation()
    assert result["status"] == "erro"
    assert result["insufficient_evidence"] is None
    assert "429" in result["error"]


def test_call_llm_retries_transient_api_errors(monkeypatch):
    """Retry a transient API error with exponential backoff."""
    api_error = errors.ClientError(429, {"error": {"message": "Rate limit"}})
    response = SimpleNamespace(text='{"answer":"ok"}')
    generate_content = Mock(side_effect=[api_error, response])
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    sleep = Mock()
    monkeypatch.setattr(rag.time, "sleep", sleep)
    assert rag.call_llm(client, "gemini-test", "question") is response
    assert generate_content.call_count == 2
    sleep.assert_called_once_with(1)


def test_call_llm_does_not_retry_nontransient_error(monkeypatch):
    """Propagate non-retryable API errors without sleeping."""
    api_error = errors.ClientError(404, {"error": {"message": "Model missing"}})
    generate_content = Mock(side_effect=api_error)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    sleep = Mock()
    monkeypatch.setattr(rag.time, "sleep", sleep)
    with pytest.raises(errors.APIError):
        rag.call_llm(client, "gemini-test", "question")
    assert generate_content.call_count == 1
    sleep.assert_not_called()



def test_call_llm_gives_up_after_max_retries(monkeypatch):
    """Stop retrying after the configured API attempt limit."""
    api_error = errors.ServerError(503, {"error": {"message": "Unavailable"}})
    generate_content = Mock(side_effect=api_error)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    sleep = Mock()
    monkeypatch.setattr(rag.time, "sleep", sleep)
    with pytest.raises(errors.APIError):
        rag.call_llm(client, "gemini-test", "question")
    assert generate_content.call_count == rag.MAX_API_RETRIES
    assert [c.args[0] for c in sleep.call_args_list] == [1, 2]


def test_generate_answer_api_error_after_invalid_output_stops(monkeypatch, reviews):
    """Stop generation when an API error follows invalid output."""
    mock_retrieval(monkeypatch, reviews)
    api_error = errors.ServerError(503, {"error": {"message": "Unavailable"}})
    llm = Mock(side_effect=[SimpleNamespace(text="not json"), api_error])
    monkeypatch.setattr(rag, "call_llm", llm)
    result = run_generation()
    assert result["status"] == "erro"
    assert "503" in result["error"]
    assert llm.call_count == 2


def test_generate_answer_empty_model_text_is_retried(monkeypatch, reviews, grounded):
    """Retry when the model returns an empty text response."""
    mock_retrieval(monkeypatch, reviews)
    llm = mock_llm(monkeypatch, "", grounded)
    assert run_generation()["status"] == "respondida"
    assert llm.call_count == 2


def test_generate_answer_uses_normalized_question(monkeypatch, reviews, grounded):
    """Pass the normalized retrieval query to the model and result."""
    mock_retrieval(monkeypatch, reviews)
    llm = mock_llm(monkeypatch, grounded)
    result = run_generation()
    assert result["question"] == "Produto não entregue?"
    assert "Produto não entregue?" in llm.call_args.args[2]


@pytest.mark.parametrize("flag", ["--top-k", "--min-citations"])
def test_main_rejects_non_positive_arguments(monkeypatch, flag):
    """Reject zero-valued CLI options before loading dependencies."""
    monkeypatch.setattr(sys, "argv", ["rag", "pergunta", flag, "0"])
    with pytest.raises(SystemExit):
        rag.main()


@pytest.mark.parametrize("reason", rag.INSUFFICIENCY_REASONS)
def test_system_instruction_documents_every_reason(reason):
    """Include every supported insufficiency reason in the prompt."""
    assert reason in rag.SYSTEM_INSTRUCTION