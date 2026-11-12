"""Manual smoke test: confirm the Gemini key and model in .env respond.

Makes one real API call; it is not part of the pytest suite.
Run from the project root: python scripts/check_gemini_connection.py
"""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types


def main():
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não configurada no arquivo .env"
        )

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000),
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=(
                "Responda em português, em uma frase: "
                "qual é a finalidade de um sistema RAG?"
            ),
        )

        if not response.text:
            raise RuntimeError(
                "A API respondeu, mas não retornou texto."
            )

        print(f"Modelo: {model}")
        print(f"Resposta: {response.text}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
