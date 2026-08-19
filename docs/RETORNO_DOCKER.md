# Retorno ao Docker

## O que foi ajustado

- Frontend volta a encaminhar `/api` para `http://api:8000`.
- API usa `DATABASE_URL_DOCKER`, sem depender da URL local.
- PostgreSQL do Docker é publicado em `localhost:5433`, evitando conflito com o PostgreSQL do Windows em `5432`.
- Alembic mantém o driver `psycopg` 3.
- Containers da API instalam dependências de autenticação e Gemini.
- Locks do npm usam o registro público.
- Migrations deixam de ser ignoradas pelo Git.
- Criação do administrador pode ser executada dentro do container.

## `.env` local

Use as duas URLs:

```env
POSTGRES_PORT=5433
DATABASE_URL=postgresql+psycopg://nexus:change-this-local-password@localhost:5433/nexus
DATABASE_URL_DOCKER=postgresql+psycopg://nexus:change-this-local-password@db:5432/nexus
```

A senha em `POSTGRES_PASSWORD`, `DATABASE_URL` e `DATABASE_URL_DOCKER` deve ser a mesma.

## Primeiro início limpo

Como ainda não há dados importantes, remova volumes antigos antes do primeiro build corrigido:

```powershell
docker compose down -v --remove-orphans
docker compose build --no-cache
docker compose up -d
```

Depois:

```powershell
docker compose ps
docker compose logs api --tail 100
docker compose logs web --tail 100
```

## Criar o primeiro administrador

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create-admin-docker.ps1
```
