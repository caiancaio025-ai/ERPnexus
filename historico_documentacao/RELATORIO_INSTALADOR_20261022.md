> DOCUMENTO HISTÓRICO (V1/V2). Para a versão atual de 26/10/2026, use `LEIA_PRIMEIRO_INSTALACAO.md` e `RELATORIO_AJUSTES_ESTOQUE_V3_20261026.md`.

# SÊNTICO Green — Relatorio tecnico de montagem do kit

**Data:** 22/10/2026
**Fonte:** `SENTICO_GREEN_DEV_AUDITADO_20261021.zip` (versao sanitizada de referencia `c515372`).

## Escopo

Entrega de desenvolvimento isolada de producao, com codigo da API e Web, migrations e testes, Docker Compose, Caddy, documentacao atualizada e instalador PowerShell/Windows.

## Problemas corrigidos ou tratados

1. **PowerShell:** comandos copiados colados sem separacao causavam `Dockerfile.devif`, `Greendocker`, `pscurl.exe` e `currentdocker`. O instalador e um arquivo unico, com lancador `.cmd` que elimina a necessidade de copiar varias linhas.
2. **Docker Desktop:** verifica que o engine Linux esta ativo antes de invocar Compose.
3. **PostgreSQL:** o container pode reutilizar senha inicial persistida no volume mesmo quando `.env.dev` muda. O script diferencia erro de autenticacao dos demais erros de conexao e, somente em caso de `password authentication failed`, sincroniza a senha do role de desenvolvimento `sentico_dev` via stdin do psql local; nao apaga volumes e confirma o nome do container, o projeto, a base e o usuario antes.
4. **Migrations:** `20261009_02_config_master_foundation.py` exige usuario existente. O script verifica a revisao, aplica somente ate `20261009_01`, solicita `create-admin` interativo (se necessario) e so entao `upgrade head`; aborta se encontrar banco preexistente nao reconhecido.
5. **Operacao:** verifica HTTP 200 da API, Vite e Caddy e exibe o endereco final. Todas as portas publicadas sao de loopback.
6. **Argumentos PowerShell:** o repasse para Docker Compose usa parametros nomeados com array explicito, impedindo que comandos compostos percam argumentos.
7. **Codigo original:** todos os modulos da base auditada permanecem. `apps/web/Dockerfile.dev` ja corrigido para nao exigir `.npmrc` ausente.

## Estado verificado

- Arquivos Python, JSON, TOML e Dockerfiles da base foram revisados estaticamente.
- Arquivos do Compose e migrations envolvidos foram inspecionados.
- O log enviado pelo desenvolvedor em 22/10 comprova `docker compose up -d --build` concluido e API/DB healthy, Web/gateway iniciados. A falha seguinte foi autenticacao PostgreSQL, nao build.
- Este **novo** instalador ainda nao teve execucao completa em Windows/Docker a partir daqui. Portanto nao se afirma login, migracao head ou funcionamentos de negocio aprovados.

## Proibicoes de seguranca

Nenhum `docker compose down -v`, exclusao de volumes, `alembic stamp`, git reset destrutivo, migracao na VPS, restore de banco real ou compartilhamento de credenciais. Nao usar este pacote como clone binario da VPS; use-o como ambiente de desenvolvimento.

## Arquivos de raiz

- `INICIAR_SENTICO_GREEN.cmd`
- `INSTALAR_SENTICO_DEV.ps1`
- `VERIFICAR_SENTICO_GREEN.cmd`
- `LEIA_PRIMEIRO_INSTALACAO.md`
- `RELATORIO_INSTALADOR_20261022.md`
- `codigo-fonte/` contendo API, Web, testes, migrations, Docker Compose e Caddy.


## Atualizacao — 22/10/2026 — usuario de testes adm

- Acrescentado `app/dev_seed_admin.py` somente para o Compose local `sentico-dev-entrega`.
- Conta solicitada: `adm` / `adm@.com.br` / `adm` / `123` (somente desenvolvimento).
- Protecao dupla: APP_ENV=development + SENTICO_DEV_TEST_ACCOUNT=1 e banco `sentico_dev` validado.
- `LoginInput` permite `123` apenas para o identificador `adm` com as duas protecoes; demais logins exigem minimo 8 caracteres.
- Instalador cria a conta apos a migration `20261009_01`, antes da `20261009_02`, sem alterar usuarios preexistentes.
- Testes de sintaxe, manifestos, arquivos do ZIP e validacao funcional limitada ao ambiente disponivel.
- A instalacao Docker/migrations/login deve ser validada na maquina Windows de destino.

## Atualização de 22/10 — Estoque técnico

O instalador agora valida o head Alembic `20261022_01`. Atualiza também um banco local que já esteja na revisão `20261013_02` sem recriar volumes. Consulte `RELATORIO_IMPLEMENTACAO_ESTOQUE.md`.


## Atualização Estoque V2 (22/10)
Instalador atualizado para a revisão Alembic `20261022_02`; mantém o PostgreSQL existente quando revision `20261022_01`, preserva volumes e não atinge a VPS. Veja RELATORIO_AJUSTES_ESTOQUE_V2_20261022.md.
