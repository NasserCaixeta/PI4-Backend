from app.services.categories import normalize_transaction_category


def test_normalizes_marketplace_and_retail_to_compras():
    assert normalize_transaction_category("Fisia Nike Ecommer - Parcela 1/4", "Outros") == "Compras"
    assert normalize_transaction_category("Shopee *Beautyenxovais", "Outros") == "Compras"
    assert normalize_transaction_category("Mercado*Mercadolivre - Parcela 1/2", "Outros") == "Compras"


def test_normalizes_housing_subscriptions_and_transfers():
    assert normalize_transaction_category("Condominio Civil Jk Sh", "Outros") == "Moradia"
    assert normalize_transaction_category("Ebn *Spotify", "Lazer") == "Assinaturas"
    assert normalize_transaction_category("Pix recebido de GEOVANA CAROLINA", "Outros") == "Transferências"


def test_keeps_known_suggestion_when_no_rule_matches():
    assert normalize_transaction_category("Cinema", "Lazer") == "Lazer"


def test_falls_back_to_outros_for_unknown_category():
    assert normalize_transaction_category("Descrição ambígua", "Categoria Inexistente") == "Outros"
