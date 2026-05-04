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
    Analise este extrato/fatura bancário PDF e extraia APENAS as transações de compras reais.

    REGRAS IMPORTANTES:
    - IGNORE completamente a seção "Pagamentos e Financiamentos" (pagamentos recebidos, parcelamentos de fatura, empréstimos, IOF, juros)
    - IGNORE linhas de resumo (fatura anterior, pagamento recebido, total de compras, etc.)
    - Estornos/devoluções devem ter type "credit" (são devoluções de dinheiro)
    - Todas as compras normais devem ter type "debit"
    - amount deve ser sempre o valor absoluto (positivo)
    - Extraia TODAS as transações de compras, sem pular nenhuma

    Para cada transação, retorne:
    - date: data no formato YYYY-MM-DD
    - description: descrição da transação
    - amount: valor absoluto (sempre positivo)
    - type: "credit" para estornos/devoluções, "debit" para compras
    - category: uma das categorias: Alimentação, Moradia, Transporte, Lazer, Saúde, Outros

    Retorne APENAS um JSON array, sem markdown ou explicações.
    """

    response = model.generate_content([
        prompt,
        {"mime_type": "application/pdf", "data": pdf_bytes}
    ])

    print(f"[DEBUG] Gemini response.text: {repr(response.text[:500]) if response.text else 'NONE/EMPTY'}")
    print(f"[DEBUG] Gemini finish_reason: {response.candidates[0].finish_reason if response.candidates else 'NO CANDIDATES'}")
    text = response.text.strip()
    # Remove markdown code block se Gemini envolver em ```json...```
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # remove primeira linha (```json)
        text = text.rsplit("```", 1)[0]  # remove ``` final
        text = text.strip()

    return json.loads(text)
