# Camelbox Backend

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python\&logoColor=fff)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi\&logoColor=fff)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-database-4169E1?logo=postgresql\&logoColor=fff)
![Celery](https://img.shields.io/badge/Celery-background%20tasks-37814A)
![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)

Backend do **Camelbox**, uma API desenvolvida com FastAPI para sustentar uma aplicação SaaS de análise financeira. O projeto inclui autenticação, categorias, transações, extratos, dashboard, pagamentos, feedbacks, workers assíncronos e integrações externas.

## Visão geral

A API centraliza as regras de negócio do Camelbox e fornece os endpoints consumidos pelo frontend. A arquitetura usa FastAPI, SQLAlchemy assíncrono, Alembic para migrações, PostgreSQL, Celery/Redis para tarefas em background e serviços de terceiros para recursos como pagamentos e IA.

## Funcionalidades

* Autenticação e autorização de usuários.
* Gerenciamento de categorias financeiras.
* Registro e consulta de transações.
* Processamento de extratos.
* Dashboard com dados agregados.
* Feedbacks de usuários.
* Integração com pagamentos/assinaturas.
* Tarefas assíncronas com Celery e Redis.
* Estrutura preparada para integrações com IA.
* Rate limit e middlewares de segurança.
* Migrações de banco com Alembic.

## Tecnologias

* **Python 3.11+**
* **FastAPI**
* **Uvicorn**
* **SQLAlchemy Async**
* **PostgreSQL / asyncpg**
* **Alembic**
* **Pydantic / Pydantic Settings**
* **Celery**
* **Redis**
* **Stripe**
* **Google Generative AI**
* **SlowAPI**
* **Pytest**

## Estrutura do projeto

```txt
app/
├── core/       # Configurações, segurança e recursos centrais
├── models/     # Modelos do banco de dados
├── routers/    # Rotas da API
├── schemas/    # Schemas Pydantic
├── services/   # Regras de negócio e integrações
├── workers/    # Tarefas assíncronas
├── database.py # Configuração de banco
└── main.py     # Inicialização da aplicação
```

## Principais módulos da API

* `auth`: autenticação e sessão.
* `categories`: categorias financeiras.
* `transactions`: transações.
* `statements`: extratos.
* `dashboard`: dados consolidados para visualização.
* `payments`: pagamentos e planos.
* `feedback`: feedbacks de usuários.
* `health`: verificação de saúde da API.

## Como executar localmente

### Pré-requisitos

* Python 3.11+
* PostgreSQL
* Redis
* `uv` instalado

### Passo a passo

```bash
git clone https://github.com/NasserCaixeta/PI4-Backend.git
cd PI4-Backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A documentação interativa da API ficará disponível em:

```txt
http://localhost:8000/docs
```

> Em produção, a documentação pode estar desabilitada por configuração de ambiente.

## Variáveis de ambiente

Use o arquivo `.env.example` como base. Em geral, o backend precisa de configurações como:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/camelbox
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=sua_chave_secreta
ALLOWED_ORIGINS=http://localhost:5173
STRIPE_SECRET_KEY=sua_chave_stripe
GOOGLE_API_KEY=sua_chave_google_ai
```

> Não versionar chaves reais, tokens ou credenciais sensíveis.

## Migrações

```bash
uv run alembic revision --autogenerate -m "descricao_da_migracao"
uv run alembic upgrade head
```

## Testes

```bash
uv run pytest
```

## Deploy

Pull requests executam testes, migrações e a validação da imagem Docker. Um
push na `main` publica uma imagem imutável no GHCR e atualiza a VPS somente
depois que todas as verificações passam.

O deploy de produção:

* Executa Alembic uma única vez.
* Atualiza API e Celery com a mesma imagem.
* Aguarda o health check da API.
* Mantém a versão anterior disponível para rollback.
* Preserva PostgreSQL, Redis e seus volumes.

Antes do deploy, confira:

* Variáveis de ambiente.
* URL do banco PostgreSQL.
* URL do Redis.
* Configuração de CORS para o domínio do frontend.
* Migrações do Alembic.

## Frontend relacionado

* [pi4-frontend-CAMELBOX](https://github.com/NasserCaixeta/pi4-frontend-CAMELBOX)

## Próximas melhorias sugeridas

* Expandir documentação dos endpoints.
* Adicionar exemplos de payloads para autenticação, transações e extratos.
* Documentar fluxo de pagamentos.
* Expandir testes de integração das tarefas assíncronas.

## Autor

Desenvolvido por [Nasser Caixeta](https://github.com/NasserCaixeta).
