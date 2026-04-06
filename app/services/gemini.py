import json

import google.generativeai as genai

from app.core.config import settings


def extract_transactions(pdf_bytes: bytes) -> list[dict]:
    """
    Envia PDF para Gemini e retorna lista de transações.

    Retorna:
    [
        {
            "date": "2024-01-15",
            "description": "SUPERMERCADO XYZ",
            "amount": 150.50,
            "type": "debit",
            "category": "Alimentação"
        },
        ...
    ]
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    prompt = """
    Analise este extrato bancário PDF e extraia todas as transações.
    Para cada transação, retorne:
    - date: data no formato YYYY-MM-DD
    - description: descrição da transação
    - amount: valor absoluto (sempre positivo)
    - type: "credit" para entradas, "debit" para saídas
    - category: uma das categorias: Alimentação, Moradia, Transporte, Lazer, Saúde, Outros

    Retorne APENAS um JSON array, sem markdown ou explicações.
    """

    response = model.generate_content([
        prompt,
        {"mime_type": "application/pdf", "data": pdf_bytes}
    ])

    return json.loads(response.text)
