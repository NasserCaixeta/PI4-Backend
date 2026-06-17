import pytest

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
