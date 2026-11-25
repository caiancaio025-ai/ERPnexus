> **LEIA PRIMEIRO:** este guia foi substituido por `LEIA_PRIMEIRO_COMPATIBILIDADE_V14.md`, que descreve o instalador atual por estrutura de dados, sem nomes obrigatorios. Os detalhes de nomes fixos abaixo sao historicos.

> **ATUALIZACAO 2026-10-29 - ERRO_INSPECAO_VOLUME:** se o pacote anterior parou em `ERRO_INSPECAO_VOLUME_SEM_MUDAR_DADOS`, utilize o instalador desta entrega, que identifica PGDATA 17 por marcador e exibe o erro do Docker. Os volumes continuam com os nomes ORIGINAIS `sentico-v14-recuperado_*`. Veja `LEIA_CORRECAO_INSPECAO_VOLUME_V14_20261029.md`.

# SENTICO V14 — Instalador local com volumes permanentes (29/10/2026)

## 1. INSTALAR

1. Deixe o Docker Desktop aberto (Linux containers).
2. Extraia este ZIP em uma pasta nova do Windows. **Nao misture com a pasta anterior da V14.**
3. Execute **INICIAR_SENTICO_V14.cmd**. (O antigo `INICIAR_SENTICO_GREEN.cmd` tambem redireciona para ele.)
4. Se o instalador concluir, abra **http://127.0.0.1:5284/**.
5. Entre com uma das **contas que ja existiam** no banco recuperado. O programa nao cria `adm/123`.

## 2. NOMES FIXOS — NAO DEPENDEM DA PASTA

| Dado | Nome Docker EXATO |
|---|---|
| PostgreSQL 17 | `sentico_v14_local_pgdata` |
| Fotos, documentos e anexos | `sentico_v14_local_uploads` |
| Pacotes Node da interface | `sentico_v14_local_node_modules` |

Projeto Compose fixo: `sentico-v14-local-fixo`. Todos os volumes sao declarados `external: true`: o Compose nao pode criar volumes implicitos com nomes derivados da pasta.

**Os volumes anteriores nao sao montados, alterados nem apagados:** `sentico-dev-entrega_dev_postgres_data`, `sentico-v14-recuperado_pgdata`, `sentico-v14-recuperado_uploads`, entre outros.

## 3. FONTE DE DADOS (SEM INVENTAR BANCO)

O instalador testa os arquivos nesta ordem:
1. Backup original `BACKUP_SENTICO_*\banco_postgresql.tar.gz` encontrado na Area de Trabalho (ou pasta informada por `-BackupDir`).
2. `dados_importacao\sentico-v14-recuperado_pgdata.tar.gz` fornecido neste pacote com dados, ou arquivo colocado nessa pasta.
3. Arquivos com esses nomes ao lado do instalador, na Area de Trabalho ou em Downloads.

Cada arquivo e restaurado **primeiro num container descartavel SEM rede**, com um volume temporario automatico. So aceita banco PostgreSQL 17 que abra com a role `sentico_green`, tenha uma migration reconhecida e pelo menos 12 usuarios / 292 clientes / 1.045 OS / 8 compras, preservando o criterio conhecido da recuperacao. Da preferencia a `sentico_green_sync_trial_20261019_01`, depois `sentico_green_preview`, depois `sentico_green`.

**Importante:** a copia do `sentico-v14-recuperado_pgdata.tar.gz` enviada pelo usuario contem o banco `sentico_green`, NAO o banco `sentico_green_sync_trial_20261019_01`. Isso era a causa da falha anterior. O novo instalador nao assume nomes de bancos: ele inspeciona e escolhe um candidato validado. Se nenhum candidato corresponder aos dados esperados, ele para *antes de criar um banco novo*.

Se o volume canônico ja tiver dados, o instalador **retoma**, sem extrair backup sobre ele. Se encontrar um volume com estrutura inesperada, para e deixa o volume intacto para diagnostico.

Uploads: tenta primeiro `dados_importacao\sentico-v14-recuperado_uploads.tar.gz`, depois backup de uploads antigo. O volume so e preenchido caso esteja vazio. Node_modules e reconstruido com `npm ci` na imagem Docker; o tar antigo de Node nao e necessario.

## 4. PORTAS SEM CONFLITO COM INSTALACOES ANTIGAS

- Interface: http://127.0.0.1:5284/
- API: http://127.0.0.1:8284/openapi.json
- Web Vite: http://127.0.0.1:5283/
- PostgreSQL: 127.0.0.1:5544

Portas publicadas somente no localhost. VPS e Blue/Green remoto nao sao tocados.

## 5. CONFIGURACAO PERSISTENTE

Fica em `%LOCALAPPDATA%\Sentico\V14LocalFixo\.env.v14` fora da pasta do projeto. Em futura troca de pasta, nao exclua esse arquivo nem os volumes. Nao envie o `.env.v14` a ninguem.

## 6. SEGURANCA / LIMITACOES

- Nao execute `docker compose down -v`, `docker volume rm` ou comandos de limpeza de volumes.
- Nao envie senhas, arquivos `.env`, PDFs de clientes ou backups para pedir suporte; envie somente mensagens de erro e diagnostico sem credenciais.
- O instalador NAO cria banco vazio quando o catalogo esperado nao existe.
- Nao executa Alembic se autenticacao, contagens, revisao ou operacao de escrita nao estiverem confirmadas.
- Alteracao da senha da **role PostgreSQL** so ocorre no volume novo e fixo, nao altera as senhas dos 12 usuarios do aplicativo.
- A migration modifica o banco escolhido no novo volume; preserve o backup para rollback.

## 7. TESTES EXECUTADOS PELO AUTOR DO PACOTE

Conferencia estatica do Compose (nomes external e portas), compilacao Python, sintaxe `sh -n` de scripts de recuperacao, estrutura e seguranca dos arquivos tar e integridade do ZIP. Nao foi possivel executar Docker Desktop/PowerShell do Windows neste ambiente: instalacao real, conexao TCP, migracoes e inicio Web/API dependem de homologacao na maquina do usuario. Sem declarar que a instalacao foi concluida ate ela passar na sua maquina.

Opcional para diagnosticar sem expor senhas: execute `DIAGNOSTICAR_SENTICO_V14_FIXO.cmd`.
