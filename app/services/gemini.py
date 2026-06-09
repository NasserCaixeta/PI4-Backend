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


def analyze_spending(transactions: list[dict]) -> dict:
    """
    Analisa uma lista de transações e retorna feedback estruturado de gastos.

    Retorna um dict com subscriptions, reducible_expenses e summary.
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    transactions_text = json.dumps(transactions, ensure_ascii=False, default=str)

    prompt = f"""
    Você é um consultor financeiro pessoal. Analise as seguintes transações do mês e gere um relatório de feedback financeiro estruturado.

    TRANSAÇÕES:
    {transactions_text}

    INSTRUÇÕES:
    1. Identifique todas as assinaturas e cobranças recorrentes (Spotify, Netflix, Amazon Prime, Google One, iCloud, YouTube Premium, antivírus, apps, SaaS, etc.)
    2. Identifique gastos que poderiam ser reduzidos ou eliminados, com sugestões práticas
    3. Escreva um resumo geral construtivo e motivador com os principais insights

    Retorne APENAS um JSON object, sem markdown ou explicações, neste formato exato:
    {{
      "subscriptions": [
        {{
          "name": "nome do serviço",
          "description": "descrição da transação original",
          "amount": 29.90
        }}
      ],
      "reducible_expenses": [
        {{
          "category": "categoria",
          "description": "descrição do gasto",
          "amount": 150.00,
          "suggestion": "sugestão prática de como reduzir",
          "potential_saving": 50.00
        }}
      ],
      "summary": "texto de 3 a 5 frases com análise geral, pontos positivos e principais recomendações"
    }}
    """

    response = model.generate_content(prompt)

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()

    data = json.loads(text)
    return {
        "subscriptions": data.get("subscriptions") or [],
        "reducible_expenses": data.get("reducible_expenses") or [],
        "summary": data.get("summary") or "",
    }
