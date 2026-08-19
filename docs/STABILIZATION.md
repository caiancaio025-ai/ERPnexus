# Estabilização da fundação

## Instalação limpa

Nunca copie `.venv` ou `node_modules` entre computadores. Eles são recriados no sistema de destino.

### Docker

```powershell
Copy-Item .env.example .env
docker compose build --no-cache
docker compose up -d
docker compose exec api alembic upgrade head
```

### Backend sem Docker

```powershell
cd apps\api
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[auth,ai,dev]"
alembic upgrade head
pytest
```

### Frontend

```powershell
cd apps\web
npm ci
npm run build
```

### Site

```powershell
cd apps\site
npm ci
npm run build
```

## Arquivos persistentes

Financeiro e Compras gravam anexos em `STORAGE_ROOT`. Os Compose usam volume persistente em `/app/storage`.
Não armazene anexos reais no Git.

## Verificações antes de abrir um módulo novo

- API sobe sem erro.
- Migrations chegam ao `head`.
- Testes passam.
- Web e site compilam.
- Upload continua disponível após recriar o container da API.
- `.env` real permanece fora do Git.
