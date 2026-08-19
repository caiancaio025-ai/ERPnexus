# 📍 MAPA DE CAMINHOS - CADA ARQUIVO VAI ONDE?

**Data**: 17/08/2026  
**Projeto**: NEXUS (C:\Users\{seu_usuario}\Documents\nexus)

---

## 🗂️ ESTRUTURA DE PASTAS (Seu PC)

```
C:\Users\{seu_usuario}\Documents\nexus\
├── apps/
│   ├── api/              ← BACKEND
│   │   ├── app/
│   │   │   ├── employees/           ← NOVA PASTA
│   │   │   └── finance/
│   │   ├── alembic/
│   │   │   └── versions/            ← MIGRATIONS
│   │   └── tests/
│   │
│   └── web/              ← FRONTEND
│       ├── src/
│       │   ├── features/
│       │   │   └── employees/       ← NOVA PASTA
│       │   └── ...
│       └── package.json
│
├── docs/                 ← DOCUMENTAÇÃO
│
└── ...
```

---

## 📋 LISTA COMPLETA COM CAMINHOS

### 🐍 BACKEND - apps/api (7 arquivos)

| # | Arquivo Original | Caminho Destino | Ação |
|---|---|---|---|
| 1 | `employees_models.py` | `apps/api/app/employees/models.py` | ✂️ COPIAR |
| 2 | `employees_schemas.py` | `apps/api/app/employees/schemas.py` | ✂️ COPIAR |
| 3 | `employees_service.py` | `apps/api/app/employees/service.py` | ✂️ COPIAR |
| 4 | `employees_router.py` | `apps/api/app/employees/router.py` | ✂️ COPIAR |
| 5 | `alembic_employees_migration.py` | `apps/api/alembic/versions/004_add_employees_tables.py` | 📝 RENOMEAR |
| 6 | `alembic_payroll_migration.py` | `apps/api/alembic/versions/003_add_payroll_tables.py` | 📝 RENOMEAR |
| 7 | `MIGRATION_CONTRACHEQUES.sql` | `docs/migrations/MIGRATION_CONTRACHEQUES.sql` | 📚 REFERÊNCIA |

**⚠️ Criar pasta**: `apps/api/app/employees/` (se não existir)

---

### ⚛️ FRONTEND - apps/web (2 arquivos)

| # | Arquivo Original | Caminho Destino | Ação |
|---|---|---|---|
| 8 | `employees_types.ts` | `apps/web/src/features/employees/types.ts` | ✂️ COPIAR |
| 9 | `EmployeeComponents.tsx` | `apps/web/src/features/employees/components/EmployeeComponents.tsx` | ✂️ COPIAR |

**⚠️ Criar pastas**: 
- `apps/web/src/features/employees/`
- `apps/web/src/features/employees/components/`

---

### 📖 DOCUMENTAÇÃO (7 arquivos)

| # | Arquivo Original | Caminho Destino | Descrição |
|---|---|---|---|
| 10 | `GUIA_IMPLEMENTACAO_FINAL.md` | `docs/GUIA_IMPLEMENTACAO_FINAL.md` | ⭐ **LEIA PRIMEIRO** |
| 11 | `ANALISE_SISTEMA_NEXUS_COMPLETA.md` | `docs/ANALISE_SISTEMA_NEXUS_COMPLETA.md` | Auditoria total |
| 12 | `RESUMO_CONTRACHEQUES.md` | `docs/RESUMO_CONTRACHEQUES.md` | Specs contracheques |
| 13 | `INTEGRACAO_PAYROLL_EMPLOYEES.md` | `docs/INTEGRACAO_PAYROLL_EMPLOYEES.md` | Como ligar |
| 14 | `ESTRUTURA_ARQUIVOS_CONTRACHEQUES.md` | `docs/ESTRUTURA_ARQUIVOS_CONTRACHEQUES.md` | Mapa visual |
| 15 | `INDICE_COMPLETO.md` | `docs/INDICE_COMPLETO.md` | Resumo executivo |
| 16 | `RESUMO_VISUAL_FINAL.md` | `docs/RESUMO_VISUAL_FINAL.md` | Visual bonito |

---

## ⚙️ ARQUIVOS QUE PRECISAM EDIÇÃO MANUAL

### 1️⃣ `apps/api/app/main.py`

**Adicionar import** (no topo do arquivo):
```python
from app.employees.router import router as employees_router
```

**Registrar router** (depois dos outros routers):
```python
app.include_router(employees_router)
```

---

### 2️⃣ `apps/api/alembic/versions/` - RENOMEAR FILES

**Arquivo 1**:
- Original: `alembic_employees_migration.py`
- Novo nome: `004_add_employees_tables.py`
- ⚠️ **Verificar se já existe 003 ou 002**

**Arquivo 2**:
- Original: `alembic_payroll_migration.py`
- Novo nome: `003_add_payroll_tables.py` (ou próximo número disponível)
- ⚠️ **Editar revision ID e down_revision no arquivo**

---

### 3️⃣ `apps/web/src/features/employees/` - CRIAR ARQUIVO __init__

Não precisa em TypeScript/React, pule se tiver erro.

---

## 🚀 ORDEM DE IMPLEMENTAÇÃO

### ✅ PASSO 1: Criar Pastas
```bash
# Backend
mkdir -p C:\Users\{seu_usuario}\Documents\nexus\apps\api\app\employees

# Frontend
mkdir -p C:\Users\{seu_usuario}\Documents\nexus\apps\web\src\features\employees\components

# Docs (se não existir)
mkdir -p C:\Users\{seu_usuario}\Documents\nexus\docs\migrations
```

### ✅ PASSO 2: Copiar Arquivos Backend

```
FROM: C:\Users\{seu_usuario}\Downloads\NEXUS_ESTRATEGIA_A_COMPLETA\
TO:   C:\Users\{seu_usuario}\Documents\nexus\apps\api\

employees_models.py      → apps/api/app/employees/models.py
employees_schemas.py     → apps/api/app/employees/schemas.py
employees_service.py     → apps/api/app/employees/service.py
employees_router.py      → apps/api/app/employees/router.py
```

### ✅ PASSO 3: Copiar Migrations

```
FROM: C:\Users\{seu_usuario}\Downloads\NEXUS_ESTRATEGIA_A_COMPLETA\
TO:   C:\Users\{seu_usuario}\Documents\nexus\apps\api\alembic\versions\

alembic_employees_migration.py → RENOMEAR para 004_add_employees_tables.py
alembic_payroll_migration.py   → RENOMEAR para 003_add_payroll_tables.py
```

### ✅ PASSO 4: Copiar Frontend

```
FROM: C:\Users\{seu_usuario}\Downloads\NEXUS_ESTRATEGIA_A_COMPLETA\
TO:   C:\Users\{seu_usuario}\Documents\nexus\apps\web\

employees_types.ts       → apps/web/src/features/employees/types.ts
EmployeeComponents.tsx   → apps/web/src/features/employees/components/EmployeeComponents.tsx
```

### ✅ PASSO 5: Copiar Documentação

```
FROM: C:\Users\{seu_usuario}\Downloads\NEXUS_ESTRATEGIA_A_COMPLETA\
TO:   C:\Users\{seu_usuario}\Documents\nexus\docs\

GUIA_IMPLEMENTACAO_FINAL.md
ANALISE_SISTEMA_NEXUS_COMPLETA.md
RESUMO_CONTRACHEQUES.md
INTEGRACAO_PAYROLL_EMPLOYEES.md
ESTRUTURA_ARQUIVOS_CONTRACHEQUES.md
INDICE_COMPLETO.md
RESUMO_VISUAL_FINAL.md
MIGRATION_CONTRACHEQUES.sql
```

### ✅ PASSO 6: Editar main.py (Manual)

```python
# Abrir: apps/api/app/main.py

# Adicionar no topo:
from app.employees.router import router as employees_router

# Adicionar depois dos outros routers:
app.include_router(employees_router)

# Resultado esperado:
# GET  http://localhost:8000/api/employees
# POST http://localhost:8000/api/employees
# etc
```

### ✅ PASSO 7: Executar Migrations

```bash
cd C:\Users\{seu_usuario}\Documents\nexus\apps\api

alembic upgrade head
```

### ✅ PASSO 8: Testar

```bash
# Terminal 1 - Backend
cd apps/api
python -m uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd apps/web
npm run dev

# Browser
http://localhost:8000/docs  # Ver endpoints
http://localhost:5173       # Frontend
```

---

## 🎯 ESTRUTURA FINAL ESPERADA

```
C:\Users\{seu_usuario}\Documents\nexus\
│
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── employees/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── models.py           ✨ NOVO
│   │   │   │   ├── schemas.py          ✨ NOVO
│   │   │   │   ├── service.py          ✨ NOVO
│   │   │   │   └── router.py           ✨ NOVO
│   │   │   ├── finance/
│   │   │   ├── auth/
│   │   │   └── main.py                 ✏️ EDITAR
│   │   │
│   │   ├── alembic/
│   │   │   └── versions/
│   │   │       ├── 001_...py
│   │   │       ├── 002_...py
│   │   │       ├── 003_add_payroll_tables.py        ✨ NOVO
│   │   │       └── 004_add_employees_tables.py      ✨ NOVO
│   │   │
│   │   └── tests/
│   │
│   └── web/
│       └── src/
│           └── features/
│               ├── employees/                        ✨ NOVO
│               │   ├── types.ts                      ✨ NOVO
│               │   ├── employees.css                 (criar depois)
│               │   └── components/
│               │       └── EmployeeComponents.tsx   ✨ NOVO
│               ├── finance/
│               ├── auth/
│               └── ...
│
└── docs/
    ├── GUIA_IMPLEMENTACAO_FINAL.md               ✨ NOVO
    ├── ANALISE_SISTEMA_NEXUS_COMPLETA.md        ✨ NOVO
    ├── RESUMO_CONTRACHEQUES.md                  ✨ NOVO
    ├── INTEGRACAO_PAYROLL_EMPLOYEES.md          ✨ NOVO
    ├── ESTRUTURA_ARQUIVOS_CONTRACHEQUES.md      ✨ NOVO
    ├── INDICE_COMPLETO.md                       ✨ NOVO
    ├── RESUMO_VISUAL_FINAL.md                   ✨ NOVO
    └── migrations/
        └── MIGRATION_CONTRACHEQUES.sql          ✨ NOVO
```

---

## ✅ CHECKLIST DE CAMINHOS

- [ ] Pasta `apps/api/app/employees/` criada
- [ ] Pasta `apps/web/src/features/employees/` criada
- [ ] Pasta `apps/web/src/features/employees/components/` criada
- [ ] Pasta `docs/migrations/` criada
- [ ] `employees_models.py` → `apps/api/app/employees/models.py`
- [ ] `employees_schemas.py` → `apps/api/app/employees/schemas.py`
- [ ] `employees_service.py` → `apps/api/app/employees/service.py`
- [ ] `employees_router.py` → `apps/api/app/employees/router.py`
- [ ] `alembic_employees_migration.py` → `apps/api/alembic/versions/004_*`
- [ ] `alembic_payroll_migration.py` → `apps/api/alembic/versions/003_*`
- [ ] `employees_types.ts` → `apps/web/src/features/employees/types.ts`
- [ ] `EmployeeComponents.tsx` → `apps/web/src/features/employees/components/`
- [ ] Todos os `.md` → `docs/`
- [ ] `main.py` editado (router registrado)
- [ ] Migrations renomeadas e com IDs corretos
- [ ] `alembic upgrade head` executado
- [ ] API testada em `/docs`
- [ ] Frontend compilando (npm run build)

---

## 🐛 TROUBLESHOOTING COMUM

### Erro: "Module not found: app.employees"
```
❌ Solução: Pasta apps/api/app/employees/ não existe
✅ Criar pasta: mkdir apps/api/app/employees
✅ Copiar arquivos
```

### Erro: "Alembic revision conflict"
```
❌ Solução: Número de migration duplicado
✅ Verificar: apps/api/alembic/versions/
✅ Renomear: 003_* e 004_* sem duplicar
```

### Erro: "TypeScript not found: employees"
```
❌ Solução: Pasta apps/web/src/features/employees não existe
✅ Criar: mkdir -p apps/web/src/features/employees/components
```

---

## 📲 PRÓXIMA GERAÇÃO: ZIPs SEPARADOS

Vou gerar **4 ZIPs separados** para facilitar:

```
📦 NEXUS_BACKEND_API.zip
   └─ Apenas arquivos de apps/api
   └─ Tudo pronto para apps/api/app/employees/
   └─ Migrations prontos para renomear

📦 NEXUS_FRONTEND_WEB.zip
   └─ Apenas arquivos de apps/web
   └─ Tudo pronto para apps/web/src/features/employees/

📦 NEXUS_MIGRATIONS.zip
   └─ Apenas migrations
   └─ Renomear e copiar para apps/api/alembic/versions/

📦 NEXUS_DOCUMENTACAO.zip
   └─ Apenas documentação
   └─ Copiar para docs/
```

---

**Quer que eu gere esses ZIPs agora?** 🚀
