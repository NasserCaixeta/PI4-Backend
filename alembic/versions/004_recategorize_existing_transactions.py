"""Recategorize existing transactions

Revision ID: 004
Revises: 003
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORY_KEYWORDS = {
    "Transferências": [
        "pix enviado",
        "pix recebido",
        "pagamento de fatura",
        "pagamento da fatura",
        "resgate rdb",
        "valor adicionado",
        "transferencia",
        "transferência",
    ],
    "Moradia": [
        "condominio",
        "condomínio",
        "aluguel",
        "energia",
        "conta de luz",
        "agua",
        "água",
        "internet residencial",
    ],
    "Assinaturas": [
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
    "Compras": [
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
    "Saúde": [
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
    "Transporte": [
        "uber",
        "99app",
        "99 app",
        "combustivel",
        "combustível",
        "posto",
        "estacionamento",
        "passagem",
    ],
    "Alimentação": [
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
}


def upgrade() -> None:
    connection = op.get_bind()
    category_ids = dict(
        connection.execute(
            sa.text("SELECT name, id FROM categories WHERE user_id IS NULL")
        ).all()
    )

    for category, keywords in CATEGORY_KEYWORDS.items():
        category_id = category_ids.get(category)
        if not category_id:
            continue
        conditions = " OR ".join(
            f"lower(description) LIKE lower(:keyword_{index})"
            for index, _ in enumerate(keywords)
        )
        params = {f"keyword_{index}": f"%{keyword}%" for index, keyword in enumerate(keywords)}
        params["category_id"] = category_id
        connection.execute(
            sa.text(
                f"""
                UPDATE transactions
                SET category_id = :category_id
                WHERE {conditions}
                """
            ),
            params,
        )


def downgrade() -> None:
    pass
