# SÊNTICO V14 — correção da migration em transação somente leitura

## O que aconteceu

O banco restaurado autentica e o Alembic inicia, mas a transação da API está em modo `read-only` (`psycopg.errors.ReadOnlySqlTransaction`, SQLSTATE `25006`). A revisão permaneceu `20261013_02` na tentativa informada, pois o PostgreSQL usa DDL transacional. Isso deve ser verificado novamente antes de prosseguir.

## O que muda

- **Não altera** o volume original `sentico-dev-entrega_dev_postgres_data` e não restaura o backup novamente.
- A etapa `07B` roda uma prova de gravação pelo **mesmo SQLAlchemy e DATABASE_URL do Alembic**, usando uma tabela temporária cuja transação é revertida.
- Confere identidade da cópia, montagem em leitura/gravação e se o servidor NÃO está em recuperação (`pg_is_in_recovery() = false`).
- Se o estado for especificamente somente leitura, faz `ALTER ROLE sentico_green IN DATABASE sentico_green_sync_trial_20261019_01 SET default_transaction_read_only = off` **somente na cópia**, usando uma única conexão administrativa com `PGOPTIONS` de escrita. Não executa `ALTER SYSTEM` nem modifica outras roles/bancos.
- A API testa uma **nova conexão** após o ajuste. Se continuar somente leitura, o instalador para antes das migrations.
- Não cria novo usuário ERP, não altera senhas, não apaga volumes. Preserva o `.env.recuperacao` existente.

## Instalação

1. Faça cópia dos arquivos atuais do projeto. Mantenha o backup `BACKUP_SENTICO_20261028_103320` e os volumes Docker.
2. Extraia a **atualização** sobre a pasta principal da V14 (a que contém `INICIAR_SENTICO_GREEN.cmd`). Preserve a estrutura de diretórios.
3. Com o Docker Desktop aberto, execute o `.cmd` usual.
4. Procure `=== 07B - VERIFICAR ESCRITA REAL NA COPIA... ===` e `API_SQLALCHEMY_ESCRITA_TRANSACIONAL=OK`, antes das migrations. Se falhar, envie o identificador `ERRO_COPIA_...` sem segredos.
5. Depois de iniciar, confira login de usuário existente, dados de OS/Clientes e novas funções de Estoque. Não publicar na VPS sem homologação.

## Limitações

Executada verificação estática do PowerShell, compilação Python, testes unitários do preflight e integridade dos ZIPs. **Não foi possível testar Docker Desktop/PostgreSQL real neste ambiente.** A configuração de leitura pode ter outra origem, e nesse caso o instalador interromperá em vez de tentar correções destrutivas.
