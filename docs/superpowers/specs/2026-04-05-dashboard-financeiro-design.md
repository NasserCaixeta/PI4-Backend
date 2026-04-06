# Sub-projeto 4: Dashboard Financeiro

## Resumo

Dashboard para visualização e gestão de transações financeiras extraídas dos extratos bancários. Inclui CRUD de categorias, edição de transações e métricas agregadas com comparativo de períodos.

## Decisões de Design

| Aspecto | Decisão |
|---------|---------|
| Categorias default | Seed global (`user_id=null`, `is_default=true`) |
| Sugestão Gemini | Auto-aplicar categoria na extração |
| Dashboard | Completo (totais + por categoria + comparativo) |
| Filtro período | Mês específico + range customizado |
| Deletar categoria | Move transações para "Outros" |
| Edição transação | Categoria + descrição (valor/data readonly) |
| Deletar transação | Sim, individualmente |
| Arquitetura | Routers separados (/categories, /transactions, /dashboard) |

## Estrutura de Arquivos

```
app/
├── routers/
│   ├── categories.py      # CRUD categorias
│   ├── transactions.py    # CRUD transações
│   └── dashboard.py       # Métricas e resumos
├── schemas/
│   ├── categories.py      # Schemas de categoria
│   ├── transactions.py    # Schemas de transação
│   └── dashboard.py       # Schemas de dashboard
└── services/
    └── dashboard.py       # Lógica de cálculo de métricas
```

## Endpoints

### Categorias

```
GET    /categories           → Lista categorias (default + do usuário)
POST   /categories           → Cria categoria personalizada
PATCH  /categories/{id}      → Atualiza categoria (só as próprias)
DELETE /categories/{id}      → Deleta categoria (move transações para "Outros")
```

**Regras:**
- `GET` retorna categorias onde `user_id = current_user.id OR is_default = true`
- `POST` cria com `user_id = current_user.id` e `is_default = false`
- `PATCH/DELETE` só permite em categorias onde `user_id = current_user.id`
- Ao deletar, transações órfãs vão para categoria "Outros"

**Schemas:**

```python
class CategoryCreate(BaseModel):
    name: str
    color: str | None = None   # hex: "#FF5733"
    icon: str | None = None    # nome do ícone: "shopping-cart"

class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    icon: str | None = None

# Campos não enviados = não alterar
# Para limpar color/icon, enviar string vazia ""
```

### Transações

```
GET    /transactions           → Lista transações do usuário (com filtros)
GET    /transactions/{id}      → Detalhe de uma transação
PATCH  /transactions/{id}      → Atualiza categoria e/ou descrição
DELETE /transactions/{id}      → Deleta transação
```

**Query Params para GET /transactions:**

| Param | Tipo | Descrição |
|-------|------|-----------|
| `month` | int (1-12) | Filtrar por mês |
| `year` | int | Filtrar por ano |
| `start_date` | date | Início do range |
| `end_date` | date | Fim do range |
| `category_id` | uuid | Filtrar por categoria |
| `type` | "credit" \| "debit" | Filtrar por tipo |
| `limit` | int | Paginação (default: 50) |
| `offset` | int | Paginação (default: 0) |

**Regras:**
- Se `month/year` informados, ignora `start_date/end_date`
- Transação só pode ser editada/deletada pelo dono (via `statement.user_id`)

**Schemas:**

```python
class TransactionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    description: str | None = None
```

### Dashboard

```
GET /dashboard/summary          → Resumo geral do período
GET /dashboard/by-category      → Breakdown por categoria
```

**Query Params (mesmos para ambos):**

| Param | Tipo | Descrição |
|-------|------|-----------|
| `month` | int (1-12) | Mês específico |
| `year` | int | Ano específico |
| `start_date` | date | Início do range |
| `end_date` | date | Fim do range |

Se nenhum parâmetro informado, usa mês atual.

**Response GET /dashboard/summary:**

```json
{
  "period": {"start": "2026-04-01", "end": "2026-04-30"},
  "total_income": 5000.00,
  "total_expenses": 3200.00,
  "balance": 1800.00,
  "transaction_count": 45,
  "comparison": {
    "income_change_percent": 10.5,
    "expenses_change_percent": -5.2,
    "previous_period": {"start": "2026-03-01", "end": "2026-03-31"}
  }
}
```

**Response GET /dashboard/by-category:**

```json
{
  "period": {"start": "2026-04-01", "end": "2026-04-30"},
  "categories": [
    {
      "category": {"id": "...", "name": "Alimentação", "color": "#FF6B6B", "icon": "utensils"},
      "total": 850.00,
      "percentage": 26.5,
      "transaction_count": 12,
      "comparison": {
        "change_percent": 15.2,
        "previous_total": 738.00
      }
    }
  ]
}
```

## Seed de Categorias Default

Categorias criadas no startup (se não existirem):

| Nome | Cor | Ícone |
|------|-----|-------|
| Alimentação | #FF6B6B | utensils |
| Moradia | #4ECDC4 | home |
| Transporte | #45B7D1 | car |
| Lazer | #96CEB4 | gamepad |
| Saúde | #DDA0DD | heart-pulse |
| Outros | #95A5A6 | ellipsis |

**Implementação:**
- Função `seed_default_categories()` em `app/database.py`
- Chamada no evento `lifespan` do FastAPI
- Usa `INSERT ... ON CONFLICT DO NOTHING` para ser idempotente

## Atualização da Task Celery

A task `process_statement` deve vincular `category_id` nas transações:

1. Gemini retorna `"category": "Alimentação"`
2. Task busca categoria: `SELECT id FROM categories WHERE name = 'Alimentação' AND is_default = true`
3. Salva transação com `category_id` preenchido

**Tratamento de erro:**
- Categoria não existe → usa "Outros"
- Falha na busca → `category_id = null`

## Testes

### test_categories.py
- `test_list_categories_returns_defaults`
- `test_create_custom_category`
- `test_cannot_edit_default_category`
- `test_cannot_delete_default_category`
- `test_delete_category_moves_transactions`

### test_transactions.py
- `test_list_transactions_empty`
- `test_list_transactions_with_filters`
- `test_update_transaction_category`
- `test_update_transaction_description`
- `test_delete_transaction`
- `test_cannot_access_other_user_transaction`

### test_dashboard.py
- `test_summary_empty`
- `test_summary_with_data`
- `test_summary_comparison`
- `test_by_category_breakdown`
- `test_filter_by_month`
- `test_filter_by_date_range`
