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


def mock_retrieval(monkeypatch, reviews, query="Produto não entregue?"):
    """Replace semantic retrieval with a deterministic result for the given query."""
    retrieval = {"query": query, "reviews": reviews}
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
    sleep.assert_called_once_with(5)


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
    assert [c.args[0] for c in sleep.call_args_list] == [5]


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

class FakeReadTimeout(Exception):
    """Stand-in for the HTTP backend's timeout exception."""


def test_call_llm_retries_timeout_then_succeeds(monkeypatch):
    """Retry a request timeout with the same backoff as transient API errors."""
    response = SimpleNamespace(text='{"answer":"ok"}')
    generate_content = Mock(side_effect=[FakeReadTimeout("slow"), response])
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    sleep = Mock()
    monkeypatch.setattr(rag.time, "sleep", sleep)
    assert rag.call_llm(client, "gemini-test", "question") is response
    sleep.assert_called_once_with(5)


def test_call_llm_timeout_exhausted_raises_unavailable(monkeypatch):
    """Raise LLMUnavailableError once every attempt has timed out."""
    generate_content = Mock(side_effect=FakeReadTimeout("slow"))
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    sleep = Mock()
    monkeypatch.setattr(rag.time, "sleep", sleep)
    with pytest.raises(rag.LLMUnavailableError):
        rag.call_llm(client, "gemini-test", "question")
    assert generate_content.call_count == rag.MAX_API_RETRIES
    assert [c.args[0] for c in sleep.call_args_list] == [5]


def test_call_llm_does_not_swallow_unrelated_exceptions(monkeypatch):
    """Programming errors must surface instead of being retried."""
    generate_content = Mock(side_effect=KeyError("bug"))
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    monkeypatch.setattr(rag.time, "sleep", Mock())
    with pytest.raises(KeyError):
        rag.call_llm(client, "gemini-test", "question")
    assert generate_content.call_count == 1


def test_generate_answer_unavailable_llm_is_technical_error(monkeypatch, reviews):
    """Report a persistent Gemini timeout as a technical error, not abstention."""
    mock_retrieval(monkeypatch, reviews)
    monkeypatch.setattr(
        rag, "call_llm", Mock(side_effect=rag.LLMUnavailableError("ReadTimeout: slow"))
    )
    result = run_generation()
    assert result["status"] == "erro"
    assert result["insufficient_evidence"] is None
    assert "unavailable" in result["error"]


def test_create_llm_client_sets_request_timeout(monkeypatch):
    """Build the Gemini client with the configured request timeout."""
    captured = {}
    monkeypatch.setattr(rag.genai, "Client", lambda **kwargs: captured.update(kwargs))
    rag.create_llm_client("key")
    assert captured["http_options"].timeout == rag.LLM_TIMEOUT_MS


@pytest.mark.parametrize("question", [
    "Quais são os principais problemas relatados pelos clientes?",
    "Problemas com a compra",
    "Quais reclamações relacionadas à entrega aparecem com maior frequência?",
])
def test_exploratory_questions_are_supported_in_prompt(monkeypatch, reviews, grounded, question):
    """Allow evidence-grounded exploratory synthesis without corpus-wide claims."""
    mock_retrieval(monkeypatch, reviews, query=question)
    llm = mock_llm(monkeypatch, grounded)
    result = rag.generate_answer(
        question=question,
        collection=object(),
        embedding_model=object(),
        llm_client=object(),
        llm_model="gemini-test",
    )
    assert result["status"] == "respondida"
    prompt = llm.call_args.args[2]
    assert question in prompt
    assert "sem extrapolar frequências para o corpus" in prompt
    assert "review_001" in prompt


def test_system_instruction_distinguishes_exploratory_from_vague():
    """Describe broad questions and vague questions without memorized examples."""
    instruction = rag.SYSTEM_INSTRUCTION
    assert "Perguntas exploratórias amplas" in instruction
    assert "pergunta_vaga: não é possível identificar o objeto" in instruction
    assert "não afirme quais problemas são os mais frequentes" in instruction
    assert "evidencia_insuficiente" in instruction


def test_system_instruction_does_not_embed_validation_questions():
    """Keep live validation questions out of the system instruction."""
    validation_questions = (
        "Problemas com a compra",
        "Foi bom?",
        "Quais clientes receberam reembolso em bitcoin após uma entrega realizada por drone?",
    )
    assert all(question not in rag.SYSTEM_INSTRUCTION for question in validation_questions)


def test_abstention_reason_guidance_covers_cases():
    """Verify that the prompt distinguishes abstention reasons."""
    instruction = rag.SYSTEM_INSTRUCTION.lower()

    for reason in rag.INSUFFICIENCY_REASONS:
        assert reason in instruction

    assert "não é vaga apenas porque descreve uma situação" in instruction


def test_specific_unsupported_question_preserves_abstention(monkeypatch, reviews):
    """Preserve a grounded abstention with no fabricated citations."""
    question = (
        "Quais clientes receberam reembolso em bitcoin "
        "após uma entrega realizada por drone?"
    )
    mock_retrieval(monkeypatch, reviews, query=question)
    llm = mock_llm(monkeypatch, {
        "answer": "As avaliações recuperadas não comprovam essa situação.",
        "cited_review_ids": [],
        "insufficient_evidence": True,
        "insufficiency_reason": "evidencia_insuficiente",
    })
    result = rag.generate_answer(
        question=question,
        collection=object(),
        embedding_model=object(),
        llm_client=object(),
        llm_model="gemini-test",
    )
    assert result["status"] == "abstencao"
    assert result["insufficiency_reason"] == "evidencia_insuficiente"
    assert result["cited_review_ids"] == []
    assert question in llm.call_args.args[2]
