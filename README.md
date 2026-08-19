# NEXUS Enterprise ERP

ERP modular em React/Vite, FastAPI, PostgreSQL e site institucional Astro.

## Estado atual

Implementado ou funcional:

- autenticação por sessão persistida;
- usuário administrador;
- dashboard operacional;
- módulo Financeiro;
- módulo de Compras V1;
- migrations Alembic;
- preparação de rotas para os próximos módulos.

Em desenvolvimento:

- cadastros mestres;
- permissões por função;
- Comercial;
- Laboratório;
- Estoque;
- auditoria central;
- integração Gemini.

## Início rápido no Windows com Docker

```powershell
Copy-Item .env.example .env
docker compose build --no-cache
docker compose up -d
docker compose exec api alembic upgrade head
```

Acessos locais:

- ERP: http://localhost:5173
- API: http://localhost:8000/health/live
- Swagger: http://localhost:8000/docs
- Site: http://localhost:4321

Para parar:

```powershell
docker compose down
```

Não envie `.env`, `.venv`, `node_modules`, caches, builds ou anexos reais junto com o projeto.

Leia `docs/STABILIZATION.md`, `docs/SETUP_WINDOWS.md`, `docs/SECURITY.md` e `docs/NEXT_STEPS.md`.
