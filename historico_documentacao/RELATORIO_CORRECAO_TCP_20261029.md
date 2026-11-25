# CORRECAO DE DIAGNOSTICO TCP — SÊNTICO V14 (29/10/2026)

## Problema reproduzido por inspecao

O instalador anterior executava o teste TCP como `docker compose exec db sh -c 'PGPASSWORD=... psql ... -c "SELECT 1"'`, com aspas aninhadas interpretadas por PowerShell 5.1 e Docker CLI do Windows. Os erros de stderr eram descartados. Isso podia produzir falso negativo mesmo depois do ALTER ROLE.

## Correcao

- Criado `scripts_recuperacao/verificar_tcp_copia.sh`, executado dentro do container db por STDIN (`sh -s`); a senha nao transita pelo PowerShell. Ela e lida somente da variavel `POSTGRES_PASSWORD` existente no container.
- A sondagem retorna `AUTENTICACAO_TCP=OK` ou um marcador sem segredos: `ERRO_TCP_SENHA_REJEITADA`, `ERRO_TCP_REGRA_PG_HBA`, `ERRO_TCP_ROLE_AUSENTE`, `ERRO_TCP_BANCO_AUSENTE`, `ERRO_TCP_CONEXAO_RECUSADA`, `ERRO_TCP_TIMEOUT`, `ERRO_TCP_SENHA_AMBIENTE_AUSENTE` ou `ERRO_TCP_OUTRO_SEM_EXIBIR_DADOS_SENSIVEIS`.
- So inicia outra redefinicao offline caso a senha seja **explicitamente rejeitada**. Para outros casos, para antes de modificar senha.
- Retem as travas de isolamento dos volumes e contagens existentes. Nenhuma migration antes de autenticacao TCP confirmada.

## Instalacao

Aplique o ZIP incremental na raiz da instalacao V14 de recuperacao, substituindo `INSTALAR_SENTICO_DEV.ps1` e incluindo `scripts_recuperacao/verificar_tcp_copia.sh`. Preserve `%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao` e todos os volumes. Rode o arquivo CMD existente. Nao envie senhas nem arquivos `.env`.

## Limitacoes dos testes

Arquivo shell validado por `sh -n` e por simulacoes com `psql` substituto para sucesso e erros de autenticacao. O script PowerShell foi verificado por analise estatica e a integridade do ZIP foi conferida. Nao foi possivel executar Docker Desktop/PowerShell 5.1 com o volume real do usuario neste ambiente. A recuperacao ainda nao esta homologada.
