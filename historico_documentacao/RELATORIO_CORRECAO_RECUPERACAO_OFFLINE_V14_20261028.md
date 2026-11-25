# Relatório técnico — Recuperação da autenticação V14

## Ocorrência

As tentativas anteriores falharam na configuração da role PostgreSQL `sentico_green` via conexão local/socket do banco recuperado. Como a falha exata no notebook não foi fornecida, **não foi possível reproduzir o erro real**.

## Mudança implementada

- `INSTALAR_SENTICO_DEV.ps1`: primeiro valida a conexão TCP; caso falhe, interrompe somente os serviços do projeto `sentico-v14-recuperado`, verifica que o volume da cópia não está em uso e executa o script de manutenção offline; reinicia o serviço e só continua após autenticação TCP bem-sucedida.
- `scripts_recuperacao/configurar_senha_offline.sh`: valida usuário Linux, versão PG 17, diretórios essenciais, parada do PostgreSQL e formato do segredo; roda `ALTER ROLE sentico_green` em uma única linha com `postgres --single` sem rede e sem emitir a senha. O script antigo via socket foi retirado.
- Identificação e volumes de recuperação mantidos: `sentico-v14-recuperado_pgdata`, `sentico-v14-recuperado_uploads`. Original `sentico-dev-entrega_dev_postgres_data` jamais montado pelo procedimento.
- Migrações preservadas: banco original em `20261013_02`, head esperado `20261028_01`. Não alterado o código do ERP.

## Testes executados aqui

- `sh -n` no script offline: aprovado.
- Simulação do comando offline em shell com `postgres` substituído por mock: sucesso, recusa de arquivo `postmaster.pid` e falha controlada, sem expor senha: aprovados.
- `python -m compileall` na API e migrations: aprovado.
- Conferência de arquivos e SHA256 após empacotamento: verificar manifesto incluído no pacote.

## Limitações

**Não foi executada recuperação real no Docker Desktop, nem migration em PostgreSQL real, nem build completo da Web.** O modo offline foi verificado na documentação oficial do PostgreSQL 17, mas o comportamento do banco restaurado precisa de teste local. O instalador preserva dados ao falhar, porém não garante a recuperação integral do sistema.

## Operação

Extraia o ZIP completo, execute `INICIAR_SENTICO_GREEN.cmd`, confirme a revisão e teste login, OS, Compras, Estoque, Financeiro e anexos. Preserve o backup e não publique na VPS sem homologação.
