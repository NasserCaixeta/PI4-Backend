from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any

REDUCIBLE_CATEGORIES = {"Alimentação", "Transporte", "Compras", "Lazer", "Assinaturas", "Serviços"}
PROTECTED_CATEGORIES = {"Saúde", "Educação", "Transferências"}

SUBSCRIPTION_KEYWORDS = {
    "spotify": "Spotify",
    "netflix": "Netflix",
    "amazon prime": "Amazon Prime",
    "prime video": "Prime Video",
    "google one": "Google One",
    "icloud": "iCloud",
    "youtube premium": "YouTube Premium",
    "disney": "Disney+",
    "max.com": "Max",
}

DELIVERY_KEYWORDS = {"ifood", "ifd", "delivery", "restaurante", "lanche", "pizza", "sushi"}
TRANSPORT_APP_KEYWORDS = {"uber", "99app", "99 app"}
MARKETPLACE_KEYWORDS = {"amazon", "mercado livre", "mercadolivre", "shopee", "shein", "magalu", "magazine luiza"}


def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).lower().strip()


def _money(value: float) -> float:
    return round(float(value or 0), 2)


def _contains_any(text: str, keywords: set[str] | dict[str, str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _confidence_for_cluster(count: int, total: float) -> str:
    if count >= 6 or total >= 500:
        return "high"
    if count >= 3 or total >= 180:
        return "medium"
    return "low"


def _priority(potential_saving: float | None, confidence: str) -> int:
    if potential_saving is None:
        return 20
    weight = {"high": 1.2, "medium": 1.0, "low": 0.65}.get(confidence, 0.8)
    return int(round(potential_saving * weight))


def _subscription_name(description: str) -> str | None:
    normalized = _normalize_text(description)
    for keyword, name in SUBSCRIPTION_KEYWORDS.items():
        if keyword in normalized:
            return name
    return None


def _merchant_key(description: str) -> str:
    normalized = _normalize_text(description)
    if _contains_any(normalized, DELIVERY_KEYWORDS):
        return "delivery"
    if _contains_any(normalized, TRANSPORT_APP_KEYWORDS):
        return "transport_app"
    if _contains_any(normalized, MARKETPLACE_KEYWORDS):
        return "marketplace"
    words = normalized.split()
    return " ".join(words[:2]) if words else "outros"


def _build_subscription(tx: dict[str, Any]) -> dict[str, Any] | None:
    name = _subscription_name(tx.get("description") or "")
    category = tx.get("category") or "Outros"
    if not name and category != "Assinaturas":
        return None

    amount = _money(tx.get("amount", 0))
    display_name = name or (tx.get("description") or "Assinatura").title()
    confidence = "high" if name else "medium"
    return {
        "name": display_name,
        "description": tx.get("description"),
        "amount": amount,
        "confidence": confidence,
        "reason": "Cobrança em categoria de assinaturas ou comerciante conhecido.",
        "evidence": [f"{tx.get('description')} - R$ {amount:.2f}"],
    }


def _build_opportunity(
    title: str,
    category: str,
    amount: float,
    count: int,
    saving_rate: float,
    suggestion: str,
    evidence: list[str],
) -> dict[str, Any]:
    confidence = _confidence_for_cluster(count, amount)
    potential_saving = _money(amount * saving_rate)
    return {
        "title": title,
        "category": category,
        "type": "reduce",
        "amount": _money(amount),
        "description": title,
        "potential_saving": potential_saving,
        "confidence": confidence,
        "priority": _priority(potential_saving, confidence),
        "reason": f"Foram {count} transações somando R$ {amount:.2f}.",
        "suggestion": suggestion,
        "evidence": evidence[:5],
    }


def _build_watch_item(title: str, category: str, amount: float, description: str) -> dict[str, Any]:
    return {
        "title": title,
        "category": category,
        "type": "watch",
        "amount": _money(amount),
        "description": description,
        "potential_saving": None,
        "confidence": "medium",
        "priority": 20,
        "reason": "Gasto relevante no mês, mas sem evidência suficiente para estimar economia.",
        "suggestion": "Acompanhe se foi uma compra pontual ou se deve entrar no planejamento dos próximos meses.",
        "evidence": [f"{description} - R$ {amount:.2f}"],
    }


def build_spending_context(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    debit_transactions = [tx for tx in transactions if tx.get("type", "debit") == "debit"]
    total_expenses = _money(sum(float(tx.get("amount") or 0) for tx in debit_transactions))

    category_totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    merchant_groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0.0, "count": 0, "category": "Outros", "transactions": []}
    )
    subscriptions: list[dict[str, Any]] = []
    watchlist: list[dict[str, Any]] = []

    for tx in debit_transactions:
        amount = float(tx.get("amount") or 0)
        category = tx.get("category") or "Outros"
        description = tx.get("description") or ""
        normalized = _normalize_text(description)

        category_totals[category]["total"] += amount
        category_totals[category]["count"] += 1

        merchant = _merchant_key(description)
        merchant_groups[merchant]["total"] += amount
        merchant_groups[merchant]["count"] += 1
        merchant_groups[merchant]["category"] = category
        merchant_groups[merchant]["transactions"].append(tx)

        subscription = _build_subscription(tx)
        if subscription:
            subscriptions.append(subscription)

        if amount >= 500 and category not in PROTECTED_CATEGORIES and not _contains_any(normalized, MARKETPLACE_KEYWORDS):
            watchlist.append(_build_watch_item("Gasto alto para acompanhar", category, amount, description))

    opportunities: list[dict[str, Any]] = []
    for group in merchant_groups.values():
        category = group["category"]
        if category in PROTECTED_CATEGORIES or group["count"] < 3:
            continue

        descriptions = [tx.get("description") or "" for tx in group["transactions"]]
        normalized_blob = " ".join(_normalize_text(description) for description in descriptions)
        evidence = [f"{tx.get('description')} - R$ {float(tx.get('amount') or 0):.2f}" for tx in group["transactions"]]

        if category == "Alimentação" and _contains_any(normalized_blob, DELIVERY_KEYWORDS):
            opportunities.append(_build_opportunity(
                "Delivery concentrado no mês",
                category,
                group["total"],
                group["count"],
                0.25,
                "Definir dias específicos para delivery pode reduzir cerca de 25% desse gasto.",
                evidence,
            ))
        elif category == "Transporte" and _contains_any(normalized_blob, TRANSPORT_APP_KEYWORDS):
            opportunities.append(_build_opportunity(
                "Transporte por aplicativo recorrente",
                category,
                group["total"],
                group["count"],
                0.20,
                "Agrupar trajetos ou planejar deslocamentos pode reduzir parte desse gasto.",
                evidence,
            ))
        elif category == "Compras" and _contains_any(normalized_blob, MARKETPLACE_KEYWORDS):
            opportunities.append(_build_opportunity(
                "Compras online recorrentes",
                category,
                group["total"],
                group["count"],
                0.15,
                "Criar uma lista de espera antes de comprar pode evitar compras por impulso.",
                evidence,
            ))

    for group in merchant_groups.values():
        if group["count"] == 1:
            tx = group["transactions"][0]
            amount = float(tx.get("amount") or 0)
            category = tx.get("category") or "Outros"
            description = tx.get("description") or ""
            normalized = _normalize_text(description)
            if amount >= 500 and category not in PROTECTED_CATEGORIES and _contains_any(normalized, MARKETPLACE_KEYWORDS):
                watchlist.append(_build_watch_item("Compra relevante para acompanhar", category, amount, description))

    opportunities.sort(key=lambda item: item["priority"], reverse=True)
    subscriptions.sort(key=lambda item: item["amount"], reverse=True)
    watchlist.sort(key=lambda item: item["amount"], reverse=True)

    total_potential_saving = _money(sum(item["potential_saving"] or 0 for item in opportunities))
    highlights = []
    if total_potential_saving > 0:
        highlights.append(f"Economia potencial estimada de R$ {total_potential_saving:.2f}.")
    if subscriptions:
        sub_total = _money(sum(item["amount"] for item in subscriptions))
        highlights.append(f"Assinaturas identificadas somam R$ {sub_total:.2f}/mês.")
    if opportunities:
        top = opportunities[0]
        highlights.append(f"Maior oportunidade: {top['title']} em {top['category']}.")

    return {
        "total_expenses": total_expenses,
        "category_totals": [
            {"category": category, "total": _money(data["total"]), "count": data["count"]}
            for category, data in sorted(category_totals.items(), key=lambda item: item[1]["total"], reverse=True)
        ],
        "subscriptions": subscriptions,
        "saving_opportunities": opportunities,
        "watchlist": watchlist,
        "total_potential_saving": total_potential_saving,
        "highlights": highlights,
    }


def _default_summary(context: dict[str, Any]) -> str:
    if context["saving_opportunities"]:
        return (
            "A análise encontrou oportunidades de economia com base na frequência e concentração "
            "dos seus gastos do mês. Os valores são estimativas conservadoras calculadas a partir "
            "das transações identificadas."
        )
    if context["subscriptions"]:
        return (
            "A análise identificou assinaturas no mês, mas não encontrou evidências suficientes "
            "para estimar cortes relevantes em outras categorias."
        )
    return (
        "A análise não encontrou padrões fortes de economia neste mês. Use os pontos de acompanhamento "
        "para observar gastos relevantes nos próximos períodos."
    )


def _merge_ai_text(context: dict[str, Any], ai_analysis: dict[str, Any] | None) -> dict[str, Any]:
    summary = (ai_analysis or {}).get("summary") or _default_summary(context)
    highlights = (ai_analysis or {}).get("highlights") or context["highlights"]
    if not highlights and summary:
        highlights = [summary]

    saving_opportunities = context["saving_opportunities"]
    return {
        "summary": summary,
        "highlights": highlights[:3],
        "subscriptions": context["subscriptions"],
        "saving_opportunities": saving_opportunities,
        "reducible_expenses": saving_opportunities,
        "watchlist": context["watchlist"],
        "total_potential_saving": context["total_potential_saving"],
    }


def generate_spending_analysis(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    context = build_spending_context(transactions)
    try:
        from app.services.gemini import analyze_spending_context

        ai_analysis = analyze_spending_context(context)
    except Exception:
        ai_analysis = None
    return _merge_ai_text(context, ai_analysis)
