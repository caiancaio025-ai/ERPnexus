# 📁 ESTRUTURA DE ARQUIVOS - CONTRACHEQUES

Este documento mostra exatamente onde colocar cada arquivo durante a implementação de contracheques.

---

## 🗂️ ARQUIVOS EXISTENTES (Modificar)

### 1. Backend - Models Expandidos

```
apps/api/app/finance/models.py
├─ ✅ Já existe
├─ AÇÃO: Adicionar ao final do arquivo:
│  ├── class Payroll
│  ├── class Payslip
│  ├── class PayslipDetail
│  └── class PayrollAuditEvent
└─ Linhas totais esperadas: ~350 linhas (foi ~100 antes)
```

**Como modificar**:
```python
# Ao final de apps/api/app/finance/models.py, adicionar:

# === CONTRACHEQUES (Novo) ===
class Payroll(Base):
    # ... código completo do arquivo RESUMO_CONTRACHEQUES.md
    
class Payslip(Base):
    # ...

class PayslipDetail(Base):
    # ...

class PayrollAuditEvent(Base):
    # ...
```

### 2. Backend - Schemas Expandidos

```
apps/api/app/finance/schemas.py
├─ ✅ Já existe (pequeno)
├─ AÇÃO: Adicionar schemas de contracheques
├─ Adicionar:
│  ├── class PayslipDetailCreate/Response
│  ├── class PayslipCreate/Response
│  ├── class PayrollCreate/Update/Response
│  └── class PayrollListResponse
└─ Linhas esperadas: ~80 novas linhas
```

### 3. Backend - Service Expandido

```
apps/api/app/finance/service.py
├─ ✅ Já existe (pequeno ~60 linhas)
├─ AÇÃO: Adicionar métodos de contracheque
├─ Novo:
│  ├── class FinanceService:
│  │   ├── async get_payrolls()
│  │   ├── async get_payslip()
│  │   ├── async mark_payslip_downloaded()
│  │   └── async create_audit_event()
│  └── Aproximadamente +100 linhas
└─ Total esperado: ~160 linhas
```

### 4. Backend - Router Expandido

```
apps/api/app/finance/router.py
├─ ✅ Já existe (~100 linhas)
├─ AÇÃO: Adicionar 5 novos endpoints
├─ GET /finance/payrolls (com filtros)
├─ GET /finance/payrolls/{id}
├─ GET /finance/payslips/{id}
├─ POST /finance/payslips/{id}/download
├─ GET /finance/payroll-audit
└─ Total esperado: ~200 linhas novas
```

### 5. Frontend - Dashboard Principal

```
apps/web/src/features/finance/FinanceDashboard.tsx
├─ ✅ Já existe
├─ AÇÃO: Adicionar aba "Contracheques"
├─ Modificar:
│  ├── Adicionar estado: activeTab
│  ├── Adicionar botão na barra de abas
│  └── Adicionar condicional: {activeTab === "payroll" && <PayrollTab />}
└─ Mudanças: ~15 linhas
```

**Mudança esperada**:
```typescript
// Em FinanceDashboard.tsx, após abas existentes:

<div className="flex gap-4 border-b">
  <button>Lançamentos</button>
  <button>Contas</button>
  {/* NOVO: */}
  <button onClick={() => setActiveTab("payroll")}>
    Contracheques
  </button>
</div>

{activeTab === "payroll" && <PayrollTab />}
```

---

## ✨ NOVOS ARQUIVOS (Criar)

### Backend

#### 1️⃣ Migration Alembic

```
apps/api/alembic/versions/003_add_payroll_tables.py

AÇÃO: Copiar arquivo alembic_payroll_migration.py
      Rename para 003_add_payroll_tables.py (verificar numeração)
      Editar: 
      - revision ID
      - down_revision (verificar last migration)
```

**Estrutura esperada**:
```
apps/api/alembic/versions/
├── 001_initial_schema.py
├── 002_add_laboratory.py
└── 003_add_payroll_tables.py  ← NOVO
```

### Frontend

#### 1️⃣ Types

```
apps/web/src/features/finance/types.ts

AÇÃO: Expandir arquivo existente (ou criar novo)
CONTENHA:
├── interface PayslipDetail
├── interface Payslip
├── interface Payroll
├── interface PayrollListItem
└── interface PayrollAuditEvent

LINHAS: ~100 linhas
```

**Arquivo completo esperado**:
```typescript
// apps/web/src/features/finance/types.ts

// Tipos existentes (não mexer):
export interface FinancialEntry { ... }
export interface Account { ... }

// NOVOS tipos de contracheque:
export interface PayslipDetail { ... }
export interface Payslip { ... }
export interface Payroll { ... }
export interface PayrollListItem { ... }
export interface PayrollAuditEvent { ... }
```

#### 2️⃣ Componentes

```
apps/web/src/features/finance/components/

NOVOS COMPONENTES:
├── PayrollList.tsx              (Listagem de folhas)
├── PayslipDetail.tsx            (Detalhes do contracheque)
└── PayrollAudit.tsx             (Relatório de auditoria - opcional)

AÇÃO: Criar arquivos nesta estrutura
LINHAS por componente: ~150-200 linhas
```

**Estrutura**:
```
apps/web/src/features/finance/components/
├── (existentes)
│   ├── FinancialEntryForm.tsx
│   ├── AccountSelector.tsx
│   └── ...
├── PayrollList.tsx              ← NOVO
├── PayslipDetail.tsx            ← NOVO
└── PayrollAudit.tsx             ← NOVO (se houver tempo)
```

#### 3️⃣ Feature Tab Principal

```
apps/web/src/features/finance/PayrollTab.tsx

AÇÃO: Criar novo arquivo
CONTEÚDO:
├── Estado de navegação (lista → detalhe → auditoria)
├── Importações de componentes
├── Lógica de roteamento interno
└── Integração com API

LINHAS: ~80-120 linhas
```

#### 4️⃣ CSS

```
apps/web/src/features/finance/finance.css

AÇÃO: Expandir arquivo existente
ADICIONAR:
├── .payroll-container
├── .payslip-detail
├── .payslip-header
├── .payslip-proventos
├── .payslip-descontos
├── .payslip-summary
├── .payroll-table
├── .payroll-filter
└── Media queries para mobile

LINHAS: ~100-150 novas linhas
```

---

## 🔄 WORKFLOW DE CRIAÇÃO

### Passo 1: Backend Database (1 dia)

```bash
# 1. Copiar migration
cp alembic_payroll_migration.py apps/api/alembic/versions/003_add_payroll_tables.py

# 2. Verificar numeração (pode ser 002 se houver)
# Editar arquivo com revision ID correto

# 3. Aplicar
cd apps/api
alembic upgrade head

# 4. Verificar
psql -c "\dt payroll*"
```

### Passo 2: Backend Models & Services (1 dia)

```bash
# 1. Expandir models.py
# Copiar classes Payroll, Payslip, etc do RESUMO_CONTRACHEQUES.md

# 2. Expandir schemas.py
# Copiar classes de Pydantic

# 3. Expandir service.py
# Adicionar métodos async

# 4. Expandir router.py
# Adicionar endpoints GET/POST

# 5. Testes
cd apps/api
pytest tests/test_finance.py -v
```

### Passo 3: Frontend Components (1 dia)

```bash
# 1. Criar/expandir types.ts
# cp e adicionar interfaces de contracheque

# 2. Criar componentes
touch apps/web/src/features/finance/components/PayrollList.tsx
touch apps/web/src/features/finance/components/PayslipDetail.tsx
touch apps/web/src/features/finance/PayrollTab.tsx

# 3. Expandir CSS
# Adicionar estilos em finance.css

# 4. Modificar Dashboard
# Editar FinanceDashboard.tsx para adicionar aba

# 5. Testes
cd apps/web
npm test -- Payroll
```

### Passo 4: Integration & QA (1 dia)

```bash
# 1. Iniciar servidores
cd apps/api && python -m uvicorn app.main:app --reload
cd apps/web && npm run dev

# 2. Testar fluxo completo
# Listar folhas → Clicar folha → Ver contracheques → Baixar PDF

# 3. Verificar auditoria
# Checar se eventos estão sendo registrados

# 4. Performance
# Testes de carga, queries lentas, etc
```

---

## 📋 CHECKLIST DE INTEGRAÇÃO

### Backend
- [ ] Migration criada e testada
- [ ] Models compilam sem erros
- [ ] Schemas validam dados
- [ ] Service methods funcionam
- [ ] Router endpoints respondent
- [ ] Testes unitários passam
- [ ] Testes de integração passam
- [ ] Documentação OpenAPI visível

### Frontend
- [ ] Types definidos
- [ ] Componentes compilam
- [ ] Componentes renderizam
- [ ] Integração com API funciona
- [ ] Dados aparecem corretamente
- [ ] Filtros funcionam
- [ ] Downloads funcionam
- [ ] Testes vitest passam
- [ ] Sem erros no console

### Database
- [ ] Tabelas criadas
- [ ] Índices presentes
- [ ] Constraints funcionam
- [ ] Foreign keys OK
- [ ] Dados de teste inseridos

### E2E
- [ ] Usuário pode listar folhas
- [ ] Usuário pode ver contracheque
- [ ] Usuário pode baixar PDF
- [ ] RH vê auditoria
- [ ] Registros são criados
- [ ] Sem erros de permissão

---

## 🎨 ESTRUTURA FINAL ESPERADA

```
NEXUS/
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   └── finance/
│   │   │       ├── models.py              ✅ Expandido (+140 linhas)
│   │   │       ├── schemas.py             ✅ Expandido (+80 linhas)
│   │   │       ├── service.py             ✅ Expandido (+100 linhas)
│   │   │       ├── router.py              ✅ Expandido (+200 linhas)
│   │   │       └── quote_pdf.py           (existente)
│   │   ├── alembic/
│   │   │   └── versions/
│   │   │       ├── 001_...py
│   │   │       ├── 002_...py
│   │   │       └── 003_add_payroll_tables.py  ✨ NOVO
│   │   └── tests/
│   │       ├── test_finance.py
│   │       └── test_payroll.py             ✨ NOVO
│   │
│   └── web/
│       └── src/
│           └── features/
│               └── finance/
│                   ├── FinanceDashboard.tsx          ✅ Expandido
│                   ├── PayrollTab.tsx                ✨ NOVO
│                   ├── types.ts                      ✅ Expandido
│                   ├── finance.css                   ✅ Expandido
│                   ├── components/
│                   │   ├── (existentes)
│                   │   ├── PayrollList.tsx           ✨ NOVO
│                   │   ├── PayslipDetail.tsx         ✨ NOVO
│                   │   └── PayrollAudit.tsx          ✨ NOVO (opcional)
│                   └── __tests__/
│                       ├── PayrollList.test.tsx      ✨ NOVO
│                       └── PayslipDetail.test.tsx    ✨ NOVO
│
└── docs/
    └── ANALISE_CONTRACHEQUES.md            ✨ Documentação
```

---

## 📊 ESTATÍSTICAS ESPERADAS

### Linhas de Código (LOC)

| Componente | Antes | Depois | Adicional |
|-----------|-------|--------|-----------|
| models.py | 100 | 240 | +140 |
| schemas.py | 40 | 120 | +80 |
| service.py | 60 | 160 | +100 |
| router.py | 100 | 300 | +200 |
| **Backend Total** | **300** | **820** | **+520** |
| types.ts | 30 | 130 | +100 |
| FinanceDashboard | 200 | 220 | +20 |
| PayrollTab | 0 | 120 | +120 |
| PayrollList | 0 | 150 | +150 |
| PayslipDetail | 0 | 180 | +180 |
| finance.css | 200 | 350 | +150 |
| **Frontend Total** | **430** | **1150** | **+720** |
| **Projeto Total** | **~4500** | **~5740** | **+1240** |

### Tempo Estimado

| Fase | Duração | Tarefas |
|------|---------|---------|
| 0 - Preparação | 4h | Setup, backup, testes locais |
| 1 - Backend | 6h | Models, schemas, service, router |
| 2 - Frontend | 6h | Components, types, integração |
| 3 - PDF | 4h | ReportLab, endpoint, cliente |
| 4 - Testes | 4h | Unitários, integração, E2E |
| 5 - QA | 4h | Bug fix, performance, docs |
| **Total** | **28h** | **~4 dias de dev** |

---

## 🚀 PRÓXIMAS FASES

Após contracheques funcionar:

### Fase 2 - Melhorias
```
├── PDF com assinatura digital
├── Integração ESOCIAL automática
├── Relatórios de RH
├── Dashboard de folhas processadas
└── Exportar para Excel
```

### Fase 3 - Integrações
```
├── API bancária (TED/DOC automático)
├── WhatsApp notificações
├── App mobile (React Native)
└── Certificado digital
```

### Fase 4 - Analytics
```
├── BI: dashboards de folha
├── Análise de custos
├── Forecasting de payroll
└── Alertas de anomalias
```

---

## 📞 REFERÊNCIAS

- **Modelos SQL**: `MIGRATION_CONTRACHEQUES.sql`
- **Código Alembic**: `alembic_payroll_migration.py`
- **Specs Completas**: `RESUMO_CONTRACHEQUES.md`
- **Análise Geral**: `ANALISE_SISTEMA_NEXUS_COMPLETA.md`
- **OpenAPI Docs**: `http://localhost:8000/docs` (após implementar)

---

**Última atualização**: 17/08/2026  
**Status**: Pronto para desenvolvemento  
**Revisão**: QA + Product Owner  

---

*Este documento é um mapa visual. Use-o como guia durante a implementação.*
