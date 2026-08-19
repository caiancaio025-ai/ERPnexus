# Preparação do Windows e VS Code

## 1. Pré-requisitos

Use Windows 10/11 de 64 bits com virtualização habilitada. Abra o PowerShell como administrador:

```powershell
wsl --install
wsl --update
```

Reinicie o computador. Instale o Docker Desktop e selecione o backend WSL 2. O Docker Desktop já inclui Docker Engine, CLI e Docker Compose.

Confirme:

```powershell
docker --version
docker compose version
wsl --version
```

## 2. VS Code

Instale o VS Code. Ao abrir a pasta, aceite as extensões recomendadas:

- Python
- Pylance
- Ruff
- Docker
- ESLint
- WSL

Abra o terminal integrado em PowerShell ou use `wsl` e depois `code .`.

## 3. Primeiro início

```powershell
Copy-Item .env.example .env
.\scripts\start.ps1
```

Na primeira execução, Docker e npm baixarão imagens e dependências. Aguarde os health checks.

## 4. Verificação

```powershell
docker compose ps
.\scripts\check.ps1
```

## 5. Comandos úteis

```powershell
docker compose logs -f api
docker compose logs -f web
docker compose exec api pytest
docker compose exec api alembic current
docker compose down
docker compose down -v  # apaga o banco local
```

Nunca use `down -v` na VPS ou quando precisar preservar dados.
