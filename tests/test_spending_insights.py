from app.services.spending_insights import build_spending_context


def tx(description, amount, category, date="2026-04-10"):
    return {
        "date": date,
        "description": description,
        "amount": amount,
        "type": "debit",
        "category": category,
    }


def test_detects_known_subscription_with_high_confidence():
    context = build_spending_context([
        tx("SPOTIFY PREMIUM", 21.90, "Assinaturas"),
    ])

    assert context["subscriptions"][0]["name"] == "Spotify"
    assert context["subscriptions"][0]["confidence"] == "high"
    assert context["subscriptions"][0]["amount"] == 21.90


def test_delivery_cluster_generates_conservative_saving_opportunity():
    context = build_spending_context([
        tx("IFOOD RESTAURANTE A", 50, "Alimentação"),
        tx("IFOOD RESTAURANTE B", 45, "Alimentação"),
        tx("IFOOD LANCHES", 60, "Alimentação"),
        tx("IFOOD PIZZA", 55, "Alimentação"),
    ])

    opportunity = context["saving_opportunities"][0]
    assert opportunity["category"] == "Alimentação"
    assert opportunity["type"] == "reduce"
    assert opportunity["amount"] == 210.0
    assert opportunity["potential_saving"] == 52.5
    assert opportunity["confidence"] == "medium"
    assert "4 transações" in opportunity["reason"]


def test_health_and_transfer_are_not_saving_opportunities():
    context = build_spending_context([
        tx("DROGASIL", 180, "Saúde"),
        tx("PIX ENVIADO MARIA", 500, "Transferências"),
    ])

    assert context["saving_opportunities"] == []
    assert context["watchlist"] == []


def test_single_high_shopping_expense_goes_to_watchlist_not_saving():
    context = build_spending_context([
        tx("AMAZON MARKETPLACE", 650, "Compras"),
    ])

    assert context["saving_opportunities"] == []
    assert context["watchlist"][0]["type"] == "watch"
    assert context["watchlist"][0]["amount"] == 650.0
    assert context["watchlist"][0]["potential_saving"] is None
