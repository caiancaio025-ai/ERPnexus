# Testar a V26 localmente (sem tocar na produção nem nos seus dados reais)

Este guia sobe a branch **`feat/v16-v26-outro-dev`** num ambiente Docker **isolado**, só pra você clicar e testar antes de qualquer deploy.

## É seguro?

Sim. Este ambiente usa o projeto Compose **`sentico-v14-local-fixo`** e volumes próprios (`sentico_v14_local_*`). Ele **não** usa:
- os volumes da VPS (produção);
- os volumes do instalador do outro dev (`sentico-v14-recuperado_*`);
- nenhuma credencial real.

É um banco **novo e vazio**, só pra teste. As portas também são diferentes (gateway em **5284**), então não conflita com o que você já roda em 5184.

## Jeito fácil (um clique)

1. Abra o **Docker Desktop** (containers Linux).
2. Na pasta do repositório, dê duplo clique em **`TESTAR-V26-LOCAL.cmd`**.
3. Ele cria um **admin padrão** sozinho (só na primeira vez, quando o banco está vazio).
4. Quando terminar, abra **http://127.0.0.1:5284/** e entre com:
   - **usuário:** `admin`
   - **senha:** `senticolocal2026`
   - (troque depois de entrar — vale só neste ambiente local isolado)

Pra **parar**: `docker compose -f compose.dev.yml down` (mantém o banco local pra próxima vez).
Pra **zerar** o banco local: `docker compose -f compose.dev.yml down -v`.

## Jeito manual (se preferir, ou se o .cmd falhar)

```bat
:: 1. pegar a branch
git fetch origin
git checkout feat/v16-v26-outro-dev
git pull

:: 2. criar o .env.dev (só na primeira vez) — senha LOCAL, alfanumérica
echo SENTICO_V14_PASSWORD=senticolocaldev2026> .env.dev
echo SENTICO_DB_NAME=postgres>> .env.dev

:: 3. criar os volumes locais isolados (so na primeira vez; idempotente)
docker volume create sentico_v14_local_pgdata
docker volume create sentico_v14_local_uploads
docker volume create sentico_v14_local_node_modules

:: 3b. subir o ambiente isolado
docker compose -f compose.dev.yml --env-file .env.dev up -d --build

:: 4. BOOTSTRAP (idempotente): migra, cria admin padrao se o banco estiver vazio, migra o resto
docker compose -f compose.dev.yml --env-file .env.dev exec -T api alembic upgrade 20261009_01
docker compose -f compose.dev.yml --env-file .env.dev exec -T api python scripts/criar_admin_padrao.py
docker compose -f compose.dev.yml --env-file .env.dev exec -T api alembic upgrade head
```

Pode rodar esses 3 comandos quantas vezes quiser — o admin só é criado quando não existe nenhum usuário.

> **Por que esse bootstrap?** A migration `20261009_02` exige um usuário já cadastrado. Então a ordem é: migrar até `20261009_01`, criar o admin padrão, e só então ir até o `head` (que inclui as 2 migrations novas da V26: notificações web push e histórico de atividade).
>
> **Login padrão:** `admin` / `senticolocal2026` (troque depois; vale só neste ambiente local).

## O que testar na V26

- Central de notificações, tema escuro, telas mobile, fotos em orçamento, painel personalizável.
- O **web push** (notificação no navegador) só funciona depois de gerar as chaves VAPID — não é necessário pra testar o resto. Se quiser testar push, me avise que eu te passo o passo de gerar as chaves.

## Importante

Este banco local está **vazio** (sem seus clientes/OS reais). É pra validar que a V26 **funciona e não quebra**. Se você quiser testar com uma **cópia** dos seus dados reais, me avise — eu te passo o passo de exportar o banco atual e restaurar nesse ambiente isolado (sem risco pro original).
