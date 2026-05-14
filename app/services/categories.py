import unicodedata

DEFAULT_FALLBACK_CATEGORY = "Outros"

CATEGORY_RULES = [
    (
        "Transferências",
        [
            "pix enviado",
            "pix recebido",
            "pagamento de fatura",
            "pagamento da fatura",
            "resgate rdb",
            "valor adicionado",
            "transferencia",
            "transferência",
        ],
    ),
    (
        "Moradia",
        [
            "condominio",
            "condomínio",
            "aluguel",
            "energia",
            "conta de luz",
            "agua",
            "água",
            "internet residencial",
        ],
    ),
    (
        "Assinaturas",
        [
            "spotify",
            "google one",
            "netflix",
            "prime video",
            "amazon prime",
            "icloud",
            "youtube premium",
            "max.com",
            "disney",
        ],
    ),
    (
        "Compras",
        [
            "nike",
            "fisia",
            "shein",
            "shopee",
            "amazonmktplc",
            "amazon marketplace",
            "mercadolivre",
            "mercado livre",
            "mercado*mercadolivre",
            "cea pay",
            "magazine luiza",
            "magalu",
            "americanas",
            "casas bahia",
        ],
    ),
    (
        "Saúde",
        [
            "drogasil",
            "droga raia",
            "raia drogasil",
            "farmacia",
            "farmácia",
            "hospital",
            "clinica",
            "clínica",
            "laboratorio",
            "laboratório",
        ],
    ),
    (
        "Transporte",
        [
            "uber",
            "99app",
            "99 app",
            "combustivel",
            "combustível",
            "posto",
            "estacionamento",
            "passagem",
        ],
    ),
    (
        "Alimentação",
        [
            "ifood",
            "ifd*",
            "restaurante",
            "supermercado",
            "mercado",
            "padaria",
            "panificadora",
            "lanche",
            "sushi",
            "gourmet",
            "alimentacao",
            "alimentação",
            "beer",
            "breja",
            "bar ",
        ],
    ),
]

KNOWN_CATEGORIES = {
    "Alimentação",
    "Moradia",
    "Transporte",
    "Lazer",
    "Saúde",
    "Compras",
    "Assinaturas",
    "Educação",
    "Serviços",
    "Transferências",
    "Outros",
}


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.lower().strip()


def normalize_transaction_category(description: str, suggested_category: str | None = None) -> str:
    normalized_description = _normalize_text(description)

    for category, keywords in CATEGORY_RULES:
        if any(_normalize_text(keyword) in normalized_description for keyword in keywords):
            return category

    if suggested_category in KNOWN_CATEGORIES:
        return suggested_category

    return DEFAULT_FALLBACK_CATEGORY
