> **Instalador atual:** use apenas `INICIAR_SENTICO.cmd` na raiz do pacote. Este documento descreve versões antigas e foi mantido para referência histórica. Veja `LEIA_PRIMEIRO_SENTICO.md`.

> **Atualizacao do kit com instalador (22/10/2026):** use `INICIAR_SENTICO_GREEN.cmd` na raiz do pacote. Ele pre-cadastra automaticamente o usuario **adm**, senha **123**, e-mail ficticio `adm@.com.br` no banco local e conclui migrations. Instrucoes antigas para cadastrar um administrador manualmente aplicam-se somente a instalacao manual sem o instalador. Nao usar essas credenciais em producao.

# SÊNTICO Green — Codigo de desenvolvimento

Este diretorio contem backend FastAPI, frontend React/Vite, migrations Alembic, testes e Docker Compose.

**Instalacao recomendada no Windows:** volte uma pasta e dê duplo clique em `INICIAR_SENTICO_GREEN.cmd`.
O instalador ja sabe que o codigo reside neste diretorio e gerencia a senha do banco, a criacao de administrador e as migrations na ordem correta.

**Leia:** `../LEIA_PRIMEIRO_INSTALACAO.md` e `../RELATORIO_INSTALADOR_20261022.md`.

O Compose de desenvolvimento utiliza `compose.dev.yml`, projeto isolado `sentico-dev-entrega`, com PostgreSQL novo e portas localhost. Ele compila API e Web a partir do codigo; imagens privadas da VPS nao sao distribuidas.

Nao execute `alembic upgrade head` diretamente num banco vazio: a migration `20261009_02` exige um usuario previo. Nao use o banco Blue/Green da VPS nem credenciais reais.
