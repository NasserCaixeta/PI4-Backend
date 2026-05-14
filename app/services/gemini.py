import json

import google.generativeai as genai

from app.core.config import settings


def normalize_statement_type(value: str | None) -> str:
    if value in {"bank_account", "credit_card"}:
        return value
    return "credit_card"


def extract_transactions(pdf_bytes: bytes) -> dict:
    """
    Envia PDF para Gemini e retorna lista de transações.

    Retorna um dict com statement_type e transactions.
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    prompt = """
    Analise este extrato/fatura bancário PDF, identifique o tipo do documento e extraia APENAS as transações reais.

    REGRAS IMPORTANTES:
    - IGNORE completamente a seção "Pagamentos e Financiamentos" (pagamentos recebidos, parcelamentos de fatura, empréstimos, IOF, juros)
    - IGNORE linhas de resumo (fatura anterior, pagamento recebido, total de compras, etc.)
    - Estornos/devoluções devem ter type "credit" (são devoluções de dinheiro)
    - Todas as compras normais devem ter type "debit"
    - amount deve ser sempre o valor absoluto (positivo)
    - Extraia TODAS as transações de compras, sem pular nenhuma
    - statement_type deve ser "credit_card" para fatura/cartão de crédito
    - statement_type deve ser "bank_account" para extrato de conta corrente/conta bancária com entradas e saídas reais
    - Se houver dúvida sobre o tipo do documento, use "credit_card"

    Para cada transação em transactions, retorne:
    - date: data no formato YYYY-MM-DD
    - description: descrição da transação
    - amount: valor absoluto (sempre positivo)
    - type: "credit" para estornos/devoluções, "debit" para compras
    - category: uma das categorias: Alimentação, Moradia, Transporte, Lazer, Saúde, Compras, Assinaturas, Educação, Serviços, Transferências, Outros

    Regras de categoria:
    - Alimentação: iFood, restaurantes, mercados, padarias, delivery, bares, lanches
    - Compras: Shein, Shopee, Amazon, Mercado Livre, Nike/Fisia, roupas, eletrônicos, marketplace e varejo
    - Moradia: condomínio, aluguel, energia, água, internet residencial, móveis e despesas da casa
    - Transporte: Uber, 99, combustível, estacionamento, transporte público e passagens
    - Assinaturas: Spotify, Google One, Netflix, Prime, iCloud, YouTube Premium e serviços recorrentes digitais
    - Saúde: farmácia, Drogasil/Raia, consultas, exames, hospital e plano de saúde
    - Educação: cursos, livros, escola, faculdade e plataformas de estudo
    - Serviços: prestadores de serviço, manutenção, salão e cobranças de serviço sem categoria mais específica
    - Transferências: Pix enviado/recebido, pagamento de fatura, resgate RDB e transferências entre contas
    - Lazer: eventos, jogos, cinema e entretenimento não recorrente
    - Outros: use apenas quando não houver informação suficiente para classificar

    Retorne APENAS um JSON object, sem markdown ou explicações, neste formato:
    {
      "statement_type": "credit_card",
      "transactions": []
    }
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

    data = json.loads(text)
    if isinstance(data, list):
        return {"statement_type": "credit_card", "transactions": data}

    statement_type = normalize_statement_type(data.get("statement_type"))
    transactions = data.get("transactions") or []
    return {"statement_type": statement_type, "transactions": transactions}
