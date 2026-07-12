import pytest
from datetime import date

from app.services.statement_processing import StatementProcessingError, validate_extraction


def test_validate_extraction_accepts_legacy_list_response():
    extraction = validate_extraction([
        {
            "date": "2026-04-10",
            "description": "Mercado",
            "amount": 25.5,
            "type": "debit",
            "category": "Alimentação",
        }
    ])

    assert extraction.statement_type == "credit_card"
    assert len(extraction.transactions) == 1
    assert extraction.transactions[0].description == "Mercado"
    assert extraction.transactions[0].billing_date == date(2026, 4, 10)
    assert extraction.transactions[0].date == date(2026, 4, 10)


def test_validate_extraction_rejects_invalid_transaction_type():
    with pytest.raises(StatementProcessingError):
        validate_extraction({
            "statement_type": "credit_card",
            "transactions": [
                {
                    "date": "2026-04-10",
                    "description": "Saque",
                    "amount": 100,
                    "type": "withdrawal",
                    "category": "Outros",
                }
            ],
        })


def test_validate_extraction_normalizes_unknown_statement_type_to_credit_card():
    extraction = validate_extraction({
        "statement_type": "unknown",
        "transactions": [],
    })

    assert extraction.statement_type == "credit_card"


def test_validate_extraction_accepts_billing_and_purchase_dates():
    extraction = validate_extraction({
        "statement_type": "credit_card",
        "statement_reference_date": "2026-09-15",
        "transactions": [
            {
                "date": "2026-09-10",
                "billing_date": "2026-09-10",
                "purchase_date": "2026-06-10",
                "description": "Loja Exemplo Parcela 3/6",
                "amount": 100,
                "type": "debit",
                "category": "Compras",
            }
        ],
    })

    tx = extraction.transactions[0]
    assert tx.date == date(2026, 9, 10)
    assert tx.billing_date == date(2026, 9, 10)
    assert tx.purchase_date == date(2026, 6, 10)


def test_validate_extraction_moves_credit_card_installment_to_statement_month():
    extraction = validate_extraction({
        "statement_type": "credit_card",
        "statement_reference_date": "2026-09-15",
        "transactions": [
            {
                "date": "2026-06-10",
                "billing_date": "2026-06-10",
                "description": "Loja Exemplo Parcela 3/6",
                "amount": 100,
                "type": "debit",
                "category": "Compras",
            }
        ],
    })

    tx = extraction.transactions[0]
    assert tx.billing_date == date(2026, 9, 10)
    assert tx.date == date(2026, 9, 10)
    assert tx.purchase_date == date(2026, 6, 10)


def test_validate_extraction_does_not_move_bank_account_installment():
    extraction = validate_extraction({
        "statement_type": "bank_account",
        "statement_reference_date": "2026-09-15",
        "transactions": [
            {
                "date": "2026-06-10",
                "billing_date": "2026-06-10",
                "description": "Emprestimo Parcela 3/6",
                "amount": 100,
                "type": "debit",
                "category": "Outros",
            }
        ],
    })

    tx = extraction.transactions[0]
    assert tx.billing_date == date(2026, 6, 10)
    assert tx.date == date(2026, 6, 10)
    assert tx.purchase_date is None
