"""Test Streamlit presentation using saved runs and synthetic RAG results."""

from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"
RUNS_PATH = PROJECT_ROOT / "evaluation" / "generation_runs.jsonl"


def _recorded_app(question_id: str) -> AppTest:
    """Run the real application in recorded mode for a selected question."""
    assert RUNS_PATH.is_file(), (
        "Missing evaluation/generation_runs.jsonl: recorded-mode tests require "
        "the versioned experiment artifact."
    )
    app = AppTest.from_file(str(APP_PATH), default_timeout=60).run()
    assert not app.exception, [item.message for item in app.exception]
    app.radio[0].set_value("Demonstração com resultados salvos").run()
    assert not app.exception, [item.message for item in app.exception]
    app.selectbox[0].set_value(question_id).run()
    assert not app.exception, [item.message for item in app.exception]
    return app


def _render_result(result: dict) -> AppTest:
    """Render a synthetic RAG result without loading the index or calling Gemini."""
    source = "from app import render_result\nrender_result(" + repr(result) + ")\n"
    app = AppTest.from_string(source, default_timeout=60).run()
    assert not app.exception, [item.message for item in app.exception]
    return app


def test_recorded_grounded_answer_displays_citations() -> None:
    """Show the saved grounded answer and its source review texts."""
    app = _recorded_app("Q01")
    assert len(app.expander) == 16
    assert any("Modo demonstração" in item.value for item in app.info)
    assert any("Evidências utilizadas" in item.value for item in app.subheader)
    assert not app.error


@pytest.mark.parametrize(
    ("question_id", "reason_message"),
    [
        ("Q12", "fora do escopo"),
        ("Q19", "mais detalhes"),
    ],
)
def test_recorded_abstentions_display_reason_without_evidence(
    question_id: str, reason_message: str
) -> None:
    """Display the correct abstention reason without presenting citations."""
    app = _recorded_app(question_id)
    assert any(reason_message in item.value for item in app.caption)
    assert len(app.expander) == 0
    assert not app.error


def test_technical_error_is_not_presented_as_abstention() -> None:
    """Distinguish a Gemini API failure from evidence-based abstention."""
    app = _render_result(
        {
            "status": "erro",
            "answer": "Não foi possível gerar uma resposta validada. Tente novamente.",
            "error": "API error 503: high demand",
            "cited_review_ids": [],
        }
    )
    assert any("problema técnico" in item.value for item in app.error)
    assert len(app.info) == 0
    assert any("Detalhes técnicos" in item.label for item in app.expander)


def test_limited_evidence_warning_and_review_text() -> None:
    """Display a low-evidence warning while preserving the cited review."""
    app = _render_result(
        {
            "status": "respondida",
            "answer": "Alguns consumidores relataram atrasos.",
            "limited_evidence": True,
            "cited_review_ids": ["review-1"],
            "retrieval": {
                "reviews": [
                    {"review_id": "review-1", "document": "Entrega atrasada."}
                ]
            },
        }
    )
    assert any("número limitado" in item.value for item in app.warning)
    assert len(app.expander) == 1
    assert "review-1" in app.expander[0].label


def test_missing_cited_review_is_reported() -> None:
    """Warn when a citation cannot be resolved to its original review."""
    app = _render_result(
        {
            "status": "respondida",
            "answer": "Resposta de teste.",
            "cited_review_ids": ["missing-review"],
            "retrieval": {"reviews": []},
        }
    )
    assert any("não está disponível" in item.value for item in app.warning)
    assert len(app.expander) == 0


def test_unexpected_status_is_reported() -> None:
    """Reject unknown result statuses rather than showing a grounded answer."""
    app = _render_result({"status": "unknown"})
    assert any("estado inesperado" in item.value for item in app.error)
