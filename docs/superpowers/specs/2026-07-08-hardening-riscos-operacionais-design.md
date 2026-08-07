# Hardening de Riscos Operacionais

## Objetivo

Corrigir riscos operacionais identificados no backend sem mudar o contrato principal da API, sem migrar upload ou feedback para processamento assíncrono, e sem exigir worker Celery no deploy atual.

Esta spec segue a Opção A: hardening conservador com testes de regressão.

## Escopo

Inclui:

- Corrigir reset de uso de análises no ciclo de assinatura Stripe.
- Evitar consumo de análise quando a geração de feedback falha.
- Validar `category_id` ao editar transações.
- Explicitar que Celery existe, mas não participa do fluxo ativo atual.
- Tornar a configuração de `JWT_SECRET` segura e previsível.
- Adicionar testes focados nos comportamentos corrigidos.

Não inclui:

- Migrar upload de extratos para Celery.
- Migrar geração de feedback para Celery.
- Remover Celery do projeto.
- Preparar deploy de worker Celery em VPS.
- Alterar endpoints públicos ou payloads de resposta.
- Mudar planos, limites, preços ou regras de Stripe.

## Problemas e Riscos

### Reset de uso em assinatura

`upsert_subscription()` atribui `current_period_start` antes de comparar se o período mudou. Isso impede detectar corretamente um novo ciclo e pode manter `analyses_used` acumulado entre períodos.

Risco: usuário pagante pode ficar bloqueado injustamente após renovação do ciclo.

### Consumo de análise no feedback

`/feedback/generate` chama `consume_analysis_or_raise()` antes de gerar a análise. Se a geração falhar, o usuário perde uma análise mesmo sem receber um feedback concluído.

Risco: cobrança de cota sem entrega funcional.

### Categoria inválida em transação

`PATCH /transactions/{transaction_id}` aceita qualquer UUID em `category_id` e grava diretamente. O banco pode rejeitar UUID inexistente via FK, ou aceitar categoria de outro usuário caso categorias customizadas sejam usadas.

Risco: erro 500 por integridade, vazamento lógico entre usuários, ou dados inconsistentes.

### Celery duplicado e não integrado

`app/workers/tasks.py` duplica lógica de processamento de extrato e feedback, mas os routers executam esses fluxos de forma síncrona. O deploy Railway inicia apenas migrations e Uvicorn.

Risco: manutenção divergente. Uma mudança no fluxo principal pode não ser refletida no worker.

### JWT aleatório

Sem `JWT_SECRET`, o app gera um segredo aleatório em runtime. Em dev isso invalida tokens a cada restart. Em produção isso seria inseguro e operacionalmente instável.

Risco: sessões inválidas após restart e configuração perigosa se produção subir sem segredo fixo.

## Design

### Billing

Em `app/services/billing.py`, `upsert_subscription()` deve capturar o período anterior antes de alterar o objeto:

- Ler `previous_period_start = subscription.current_period_start`.
- Atualizar campos Stripe.
- Resetar `analyses_used = 0` se `current_period_start` existir e for diferente de `previous_period_start`.

Para uma assinatura nova, `analyses_used` deve permanecer no default, exceto se for necessário inicializar explicitamente em `0` para clareza.

### Feedback

Em `app/routers/feedback.py`, o fluxo deve separar verificação de disponibilidade e consumo:

- Validar payload e duplicidade como hoje.
- Chamar `ensure_analysis_available_or_raise()` antes de criar/processar feedback.
- Criar feedback em `processing`.
- Gerar análise.
- Se a análise for concluída, preencher campos, marcar `completed` e chamar `consume_analysis_or_raise()`.
- Se a análise falhar, marcar `error` e não consumir análise.

O endpoint deve continuar retornando `201` com o status final salvo, preservando o contrato atual. Erros inesperados durante geração continuam registrados no próprio feedback como `status="error"`.

### Transações

Em `app/routers/transactions.py`, ao receber `category_id`:

- Buscar `Category` com o UUID informado.
- Permitir apenas categoria default (`is_default == true`) ou categoria cujo `user_id` seja o usuário atual.
- Se não encontrada ou não permitida, retornar erro controlado, preferencialmente `404` com `"Categoria não encontrada"`.
- Só então atribuir `transaction.category_id`.

Isso mantém compatibilidade com categorias default atuais e protege categorias customizadas futuras.

### Celery

Não integrar Celery neste pacote.

A mudança conservadora é documentar no código ou na documentação do projeto que os workers existem como infraestrutura não ativa no deploy atual. A lógica de verdade continua nos serviços chamados pelos routers.

Celery será tratado em uma feature própria posterior, com foco em execução correta em uma VPS Hostinger. Essa feature deve redesenhar o fluxo assíncrono de ponta a ponta: API enfileirando jobs, worker separado, Redis/broker, persistência de status, observabilidade e deploy.

Se houver edição em áreas duplicadas futuramente, a preferência deve ser extrair lógica compartilhada para `app/services` e fazer routers/workers chamarem o mesmo serviço, em vez de duplicar regras.

### JWT

Em `app/core/config.py`, `settings.jwt_secret` deve:

- Retornar `JWT_SECRET` quando configurado.
- Em `APP_ENV == "production"`, levantar erro claro se `JWT_SECRET` estiver ausente.
- Em dev/test, usar fallback estável e previsível para evitar invalidar tokens a cada restart, mantendo warning claro para não usar em produção.

O fallback deve ser suficientemente explícito para desenvolvimento local, por exemplo uma string fixa derivada do nome do projeto. Não deve ser usado em produção.

## Testes

Adicionar ou ajustar testes para:

- `upsert_subscription()` reseta `analyses_used` quando `current_period_start` muda.
- `upsert_subscription()` não reseta quando o período não muda.
- `/feedback/generate` não consome análise quando `generate_spending_analysis()` falha.
- `PATCH /transactions/{id}` retorna erro controlado para `category_id` inexistente.
- `PATCH /transactions/{id}` aceita categoria default válida.
- Configuração em produção sem `JWT_SECRET` falha explicitamente.
- Configuração fora de produção sem `JWT_SECRET` usa fallback estável.

Os testes existentes dependem de PostgreSQL local em `localhost:5432`. A verificação completa exige esse banco ativo. Testes unitários de billing/config podem rodar sem banco se forem isolados adequadamente.

## Critérios de Aceite

- Usuário pagante tem uso resetado corretamente em novo ciclo Stripe.
- Geração de feedback com erro não consome cota.
- Edição de transação não aceita categoria inexistente ou não permitida.
- Produção não sobe silenciosamente com segredo JWT aleatório.
- Dev/test mantêm comportamento simples sem quebrar a experiência local.
- Nenhum endpoint público muda de rota ou formato de resposta esperado.
- Celery permanece fora do caminho crítico, com seu status documentado.
- A futura integração Celery/VPS fica explicitamente fora deste pacote.
