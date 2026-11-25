# Relatório técnico — V14 PostgreSQL read-only — 29/10/2026

## Erro reproduzido pelo log

A API entrou em Alembic e iniciou o upgrade `20261013_02 -> 20261022_01`, mas recebeu `psycopg.errors.ReadOnlySqlTransaction`, SQLSTATE 25006, no `CREATE TABLE inventory_location_types`. A tentativa não autoriza concluir que o banco está corrompido.

## Origem provável

Banco Green importado possui configuração read-only por role ou database, herdada da origem. Não foi possível inspecionar a configuração do notebook neste ambiente. O script verifica a conexão real da API, o estado do servidor e a montagem antes de qualquer ajuste.

## Alterações reais

1. `INSTALAR_SENTICO_DEV.ps1`: valida `RW` do volume de recuperação no container `db`. Após iniciar a API, chama verificação real SQLAlchemy; se read-only, verifica role, database e `pg_is_in_recovery()` e altera `default_transaction_read_only` **somente** para `(sentico_green, sentico_green_sync_trial_20261019_01)`, dentro da cópia. Executa nova checagem e bloqueia migrations se ainda read-only.
2. `codigo-fonte/apps/api/scripts/verificar_escrita_recuperacao.py`: verificação de identidade e escrita com transação revertida (`CREATE TEMP TABLE ...`), sem gravar dados persistentes. Mensagens sem credenciais.
3. `LEIA_CORRECAO_READ_ONLY_V14_20261029.md`: instruções para retomar com a mesma pasta e volumes.

## Testes

- Seis simulações executadas com mocks de conexão SQLAlchemy: caminho gravável, somente leitura, recuperação PostgreSQL, identidade incorreta, permissão para DDL temporário e SQLSTATE 25006 — 6/6 aprovadas.
- Compilação Python do novo script aprovada.
- Inspeção estática dos nomes dos volumes, ordem das etapas, e proibição de execução das migrations quando a pré-validação falha.
- ZIPs auditados por CRC e SHA256.

**Não homologado:** Docker Desktop do Windows, conexão real PostgreSQL 17 e migracões Alembic em banco real. Nenhum dado do notebook foi copiado para esta entrega. Nenhuma alteração realizada na VPS.
