"""Streamlit interface for live and recorded Olist RAG results."""

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.config import CHROMA_PATH, COLLECTION_NAME, MODEL_NAME


RECORDED_RUNS_PATH = Path(__file__).resolve().parent / "evaluation" / "generation_runs.jsonl"

REASON_MESSAGES = {
    "fora_do_escopo": "A pergunta está fora do escopo das avaliações históricas disponíveis.",
    "pergunta_vaga": "A pergunta precisa de mais detalhes para identificar evidências diretas.",
    "evidencia_insuficiente": "As avaliações recuperadas não fornecem evidências suficientes.",
}


@st.cache_resource(show_spinner="Carregando índice e modelo de embeddings...")
def load_retrieval_resources():
    """Load and cache the persistent Chroma collection and embedding model."""
    # Heavy imports stay here so demo mode opens without loading them.
    import chromadb
    from sentence_transformers import SentenceTransformer

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_collection(COLLECTION_NAME)
    embedding_model = SentenceTransformer(MODEL_NAME)
    return collection, embedding_model


def render_evidence(result: dict) -> None:
    """Display original texts for the review IDs cited by the model."""
    cited_ids = result.get("cited_review_ids", [])
    reviews_by_id = {
        review["review_id"]: review
        for review in result.get("retrieval", {}).get("reviews", [])
    }

    st.subheader("Evidências utilizadas")
    st.caption(f"{len(cited_ids)} avaliação(ões) citada(s) na resposta.")

    for position, review_id in enumerate(cited_ids, start=1):
        review = reviews_by_id.get(review_id)
        if review is None:
            st.warning(f"A avaliação {review_id} não está disponível no resultado.")
            continue
        with st.expander(f"Evidência {position} · {review_id}"):
            st.write(review["document"])
            st.caption(f"Identificador da avaliação: {review_id}")


def render_result(result: dict) -> None:
    """Render grounded answers, evidence-based abstentions, or technical errors."""
    status = result.get("status")
    st.subheader("Resultado")

    if status == "erro":
        st.error("Não foi possível concluir a consulta por um problema técnico.")
        st.write(result.get("answer", "Tente novamente mais tarde."))
        with st.expander("Detalhes técnicos"):
            st.code(str(result.get("error") or "Erro não especificado."))
        return

    if status == "abstencao":
        st.info(result.get("answer", "Não há evidências suficientes para responder."))
        reason = result.get("insufficiency_reason")
        st.caption(REASON_MESSAGES.get(reason, "O sistema optou por não responder."))
        return

    if status != "respondida":
        st.error("O sistema retornou um estado inesperado.")
        return

    st.write(result["answer"])
    if result.get("limited_evidence"):
        st.warning("A resposta possui um número limitado de avaliações citadas.")
    render_evidence(result)
    st.caption(
        "A síntese considera apenas as avaliações recuperadas e não representa "
        "uma estimativa de frequência ou satisfação de todos os consumidores."
    )


@st.cache_data(show_spinner=False)
def load_recorded_runs(path: str) -> list[dict]:
    """Load the latest successful recorded run for each evaluation question."""
    latest = {}
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            question_id = record.get("question_id")
            if not question_id or record.get("status") not in {"respondida", "abstencao"}:
                continue
            if not isinstance(record.get("retrieval", {}).get("reviews"), list):
                continue
            # Preserve the last valid recorded attempt, not a subsequent API error.
            latest[question_id] = record
    return [latest[key] for key in sorted(latest)]


def render_recorded_mode() -> None:
    """Show saved experimental results without loading embeddings or calling Gemini."""
    st.info("Modo demonstração: resultados históricos do Notebook 03, sem nova execução do RAG.")
    if not RECORDED_RUNS_PATH.is_file():
        st.error("Arquivo de demonstração ausente: evaluation/generation_runs.jsonl")
        return
    try:
        runs = load_recorded_runs(str(RECORDED_RUNS_PATH))
    except (OSError, ValueError, TypeError) as exc:
        st.error("Não foi possível carregar as execuções registradas.")
        with st.expander("Detalhes técnicos"):
            st.code(f"{type(exc).__name__}: {exc}")
        return
    if not runs:
        st.warning("Não há execuções válidas para demonstração.")
        return
    options = {run["question_id"]: run for run in runs}
    selected = st.selectbox(
        "Pergunta registrada",
        options=list(options),
        format_func=lambda key: f"{key} — {options[key]['question']}",
    )
    result = options[selected]
    st.caption(f"Modelo registrado: {result.get('model', 'não informado')} · "
               f"top_k: {result.get('top_k', 'não informado')}")
    render_result(result)


def main() -> None:
    """Initialize the application and handle one question per submission."""
    st.set_page_config(
        page_title="Voice of Customer Intelligence",
        page_icon="💬",
        layout="centered",
    )
    st.title("Voice of Customer Intelligence")
    st.write("Explore experiências de consumidores registradas nas avaliações históricas da Olist.")
    st.caption("As respostas são fundamentadas nas avaliações recuperadas, com fontes verificáveis.")

    mode = st.radio(
        "Modo de utilização",
        ["Consulta ao vivo", "Demonstração com resultados salvos"],
        horizontal=True,
    )
    if mode == "Demonstração com resultados salvos":
        render_recorded_mode()
        return

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    llm_model = os.getenv("GEMINI_MODEL")

    if not api_key or not llm_model:
        st.error("Configure GEMINI_API_KEY e GEMINI_MODEL no arquivo .env para usar a aplicação.")
        st.stop()

    # Imported only for live queries; demo mode never needs the RAG stack.
    from src.rag import DEFAULT_TOP_K, create_llm_client, generate_answer

    with st.form("review_question_form"):
        question = st.text_area(
            "O que você deseja investigar?",
            placeholder="Ex.: Quais problemas os consumidores relatam sobre atrasos na entrega?",
            height=110,
        )
        submitted = st.form_submit_button("Consultar avaliações", type="primary")

    if submitted:
        question = question.strip()
        if not question:
            st.warning("Digite uma pergunta antes de consultar.")
        else:
            try:
                with st.spinner("Buscando evidências e consultando o Gemini (pode haver novas tentativas)..."):
                    collection, embedding_model = load_retrieval_resources()
                    with create_llm_client(api_key) as llm_client:
                        result = generate_answer(
                            question=question,
                            collection=collection,
                            embedding_model=embedding_model,
                            llm_client=llm_client,
                            llm_model=llm_model,
                            top_k=DEFAULT_TOP_K,
                        )
                st.session_state["last_result"] = result
            except Exception as exc:
                st.session_state.pop("last_result", None)
                st.error("Não foi possível realizar a consulta. Verifique o índice e a conexão com a API.")
                with st.expander("Detalhes técnicos"):
                    st.code(f"{type(exc).__name__}: {exc}")

    if "last_result" in st.session_state:
        render_result(st.session_state["last_result"])


if __name__ == "__main__":
    main()
