# 🔍 AUDITORIA TOTAL DO SISTEMA NEXUS
**Data**: 17/08/2026  
**Status**: Análise Estrutural Completa + Roadmap de Melhorias

---

## 📊 VISÃO GERAL DA ARQUITETURA

### Estrutura Monorepo
```
nexus/
├── apps/
│   ├── api/          (FastAPI + SQLAlchemy + PostgreSQL)
│   ├── web/          (React 19 + TypeScript + Vite)
│   └── site/         (Documentação/Landing Page)
├── docs/             (Referências arquiteturais)
├── infra/            (Docker + Caddy)
└── scripts/          (Automação + utilities)
```

### Stack Tecnológico
- **Backend**: FastAPI + SQLAlchemy 2.0 + PostgreSQL + Alembic
- **Frontend**: React 19.2.7 + TypeScript 7.0.2 + Vite 8.1.4
- **UI Components**: Lucide React + Motion (animações)
- **Routing**: React Router DOM 7.18.1
- **Database**: PostgreSQL com migrations versionadas
- **Testing**: pytest + Vitest (setup pronto)
- **Code Quality**: Ruff + TypeScript strict + mypy

---

## 📈 MÓDULOS IMPLEMENTADOS

### ✅ Backend (app/*)
| Módulo | Status | Modelos | Routers | Schemas |
|--------|--------|---------|---------|---------|
| **auth** | ✅ Operacional | User, Token, Session | Completo | JWT + Pydantic |
| **core** | ✅ Base | Base ORM | Migrations | Config |
| **dashboard** | ✅ Operacional | KPI aggregates | GET endpoints | Leitura |
| **finance** | ✅ Operacional | Entry, Account, Category, Transfer, Audit | 16 endpoints | Completo |
| **laboratory** | ✅ Operacional | WorkOrder, Quote, Equipment, Customer, Document | 28+ endpoints | Completo |
| **customers** | ✅ Operacional | Customer 360 | Completo | Completo |
| **purchasing** | ✅ Operacional | PurchaseOrder | Endpoints | Schemas |
| **inventory** | ✅ Operacional | Stock, Movement | Endpoints | Schemas |
| **commercial** | 🟡 Parcial | Structure | Básico | Não |
| **tracking** | ✅ Operacional | WorkOrder tracking | Endpoints | Schemas |
| **audit** | ✅ Base | AuditEvent genérico | Listeners | Schema |
| **reminders** | ✅ Base | Reminder events | Task queue | Schema |
| **assistant** | 🟡 Parcial | AI integration | Endpoints | Gemini API |

### ✅ Frontend (features/*)
| Feature | Status | Telas | Componentes | State |
|---------|--------|-------|-------------|-------|
| **auth** | ✅ Operacional | Login/Register | Forms | Context |
| **dashboard** | ✅ Operacional | Main KPI view | Cards, Charts | Fetching |
| **customers** | ✅ Operacional | 360 view | Detail, List | React hooks |
| **finance** | ✅ Operacional | Billing panel | Entry list, Export | Hooks |
| **laboratory** | ✅ Operacional | OS list, Detail | Quote PDF gen | Hooks |
| **purchasing** | ✅ Operacional | PO list | Basic CRUD | Hooks |

---

## 🟢 PONTOS FORTES

### 1. **Arquitetura Bem Estruturada**
- ✅ Padrão SDD (Sistema de Divisão por Feature) já implementado
- ✅ Backend separado em módulos independentes
- ✅ Frontend com features isoladas
- ✅ CSS não vaza entre modules (finance.css isolado)

### 2. **Qualidade de Código**
- ✅ TypeScript strict mode
- ✅ Ruff para linting Python
- ✅ Type hints completos em SQLAlchemy
- ✅ Pydantic v2 para validação robusta
- ✅ mypy strict para type checking

### 3. **Database & Migrations**
- ✅ SQLAlchemy ORM completo
- ✅ Alembic setup funcional
- ✅ Versionamento de migrations
- ✅ Foreign keys e constraints bem definidas
- ✅ Indexes estratégicos (company_code, date fields, status)

### 4. **Auditoria & Segurança**
- ✅ Modelo FinancialAuditEvent implementado
- ✅ Modelo LaboratoryAuditEvent com status history
- ✅ JWT authentication pronto
- ✅ User tracking (created_by fields)
- ✅ Soft delete patterns (is_deleted flags)

### 5. **API Design**
- ✅ RESTful endpoints bem estruturados
- ✅ Paginação implementada
- ✅ Filtros por período (mês/ano)
- ✅ Status filtering genérico
- ✅ Search global parcial

### 6. **Frontend Modern**
- ✅ React 19 (latest)
- ✅ TypeScript strict
- ✅ Component-based architecture
- ✅ Reusable components structure
- ✅ CSS modular por feature

---

## 🟠 ÁREAS DE MELHORIA CRÍTICAS

### 1. **Laboratório - Interface UX** 🎯
**Nível**: Alto  
**Impacto**: Usabilidade operacional

**Problemas**:
- ❌ Tabela não ocupa 100% da largura disponível
- ❌ Margens laterais grandes (layout desktop)
- ❌ Filtros espalhados (não compactos)
- ❌ KPIs desorganizados visualmente
- ❌ Modal gigante para edição de OS (deve ser página)
- ❌ Paginação não visual/clara

**Recomendações**:
```
FASE A - Refactor Layout (1-2 dias)
├── Full-width container
├── Filtros em barra única compacta
├── KPIs como cards inline
├── Tabela com scroll horizontal se necessário
└── Cabeçalho sticky

FASE B - Roteamento (1 dia)
├── /laboratorio/os/:id (página dedicada)
├── Edição completa fora de modal
├── Navegação breadcrumb
└── Back button contextual
```

**Checklist**:
- [ ] CSS refactor: `laboratory.css` → full-width layout
- [ ] Componentes: `LaboratoryFilters.tsx` (barra única)
- [ ] Página: `LaboratoryWorkOrderDetail.tsx` (nova rota)
- [ ] Modal remover de lista (usar link para página)

---

### 2. **Filtro de Período - Lógica de Data** 🎯
**Nível**: Alto  
**Impacto**: Integridade de dados

**Problema**:
- ❌ Está usando `updated_at` ao invés de `opened_at` (data_entrada)
- ❌ OS "anda de mês" quando editada

**Solução**:
```python
# ANTES (ERRADO)
WHERE DATE_PART('month', updated_at) = $1

# DEPOIS (CORRETO)
WHERE DATE_PART('month', opened_at) = $1
```

**Checklist**:
- [ ] Migration: adicionar índice em `opened_at`
- [ ] Query: `/laboratory/work-orders` usar `opened_at`
- [ ] Backend: `router.py` line ~150
- [ ] Frontend: verificar query params
- [ ] Teste: OS antiga não muda de período ao editar

---

### 3. **Indicadores & Drill-down** 🎯
**Nível**: Alto  
**Impacto**: Operacional

**Falta**:
- ❌ KPIs dinâmicos por filtro (não recalcules ao mudar período)
- ❌ Gráficos sem interatividade
- ❌ Clique em gráfico não filtra lista
- ❌ Lead time não calculado
- ❌ Alertas automáticos desligados

**Recomendações**:
```
Implementar:
├── KPI Service com cache
├── Gráficos interativos (onClick → filter)
├── Lead time calculation (TODAY - opened_at)
├── Color-coded alerts (verde/amarelo/laranja/vermelho)
└── Auto-update em real-time
```

**Checklist**:
- [ ] Backend: `laboratory/service.py` → KPI calculator
- [ ] Frontend: `LaboratoryIndicators.tsx` → click handlers
- [ ] Gráficos: integrar interatividade
- [ ] Alertas: color schema definido

---

### 4. **Auditoria Completa** 🎯
**Nível**: Médio-Alto  
**Impacto**: Compliance + Debugging

**Status Atual**:
- ✅ Modelo `LaboratoryAuditEvent` existe
- ⚠️ Não está sendo populado automaticamente
- ❌ Sem "antes/depois" (before/after)
- ❌ Sem IP/request_id tracking
- ❌ Sem aba Histórico na OS

**Implementar**:
```python
# Estrutura necessária
class AuditEvent:
    actor: User
    entity: str  # "laboratory_work_order"
    entity_id: int
    action: str  # "status_changed", "quote_created"
    before: dict
    after: dict
    timestamp: datetime
    ip_address: str
    request_id: str
```

**Checklist**:
- [ ] Middleware: capturar IP + request_id
- [ ] Listeners: hook em POST/PUT/DELETE
- [ ] Models: expandir AuditEvent (antes/depois)
- [ ] Frontend: aba "Histórico" na OS detail
- [ ] Frontend: página /laboratorio/auditoria (pesquisa global)

---

### 5. **Performance & Paginação** 🎯
**Nível**: Médio  
**Impacto**: UX em dados grandes

**Problemas**:
- ⚠️ Lazy loading parcial (eager load em alguns relacionados)
- ❌ Paginação hardcoded em 25/50/100
- ❌ Sem índices em search fields
- ❌ N+1 queries possíveis (document relationships)

**Recomendações**:
```
├── Índices em search fields:
│   ├── customer_name
│   ├── equipment_serial
│   ├── model
│   └── equipment_type
├── Query optimization:
│   ├── Explicit selectinload()
│   ├── Avoid eager load de documents
│   └── Use count() separado
└── Pagination:
    ├── Padrão: 25 por página
    ├── Opções: 50, 100
    └── Limite máximo: 500
```

**Checklist**:
- [ ] Migration: criar índices em search fields
- [ ] Service: otimizar queries (explain analyze)
- [ ] Paginação: implementar offset/limit
- [ ] Frontend: lazy load de documents

---

### 6. **Validação de Dados** 🟡
**Nível**: Médio  
**Impacto**: Qualidade de dados

**Falta**:
- ⚠️ Validação de série de equipamento (normalização)
- ⚠️ CNPJ/CPF validation (não fazer lado cliente)
- ⚠️ Validação de transição de status (não pode voltar)
- ⚠️ Validação de orçamento (pode ser 0 em triagem)

**Checklist**:
- [ ] Schemas: adicionar validators
- [ ] Backend: business rules validation
- [ ] Status flow: definir matriz de transições válidas
- [ ] Equipamento: serial normalization (upper + trim)

---

### 7. **Cobertura de Testes** 🟡
**Nível**: Médio  
**Impacto**: Confiabilidade

**Status**:
- ✅ pytest setup
- ✅ Vitest setup
- ❌ Testes não escritos (~0%)
- ❌ Sem CI/CD

**Recomendação** (Fase E):
```
Backend (pytest):
├── test_laboratory_router.py
├── test_laboratory_service.py
├── test_audit_events.py
├── test_financial_entries.py
└── test_auth.py

Frontend (vitest):
├── LaboratoryFilters.test.tsx
├── LaboratoryIndicators.test.tsx
└── FinanceDashboard.test.tsx
```

**Checklist**:
- [ ] Criar structure em `apps/api/tests/laboratory/`
- [ ] Criar structure em `apps/web/src/features/__tests__/`
- [ ] GitHub Actions CI configurado
- [ ] Coverage mínimo: 60%

---

### 8. **Documentação de API** 🟡
**Nível**: Baixo  
**Impacto**: Developer experience

**Falta**:
- ⚠️ OpenAPI/Swagger desligado
- ⚠️ Sem exemplos de request/response
- ⚠️ Sem documentação de erros
- ⚠️ Sem rate limiting documentado

**Checklist**:
- [ ] Ativar FastAPI docs: `/docs`
- [ ] Adicionar docstrings em routers
- [ ] Exemplos em schemas (Config examples)
- [ ] Response models com examples

---

## 🚀 IMPLEMENTAÇÃO: CONTRACHEQUES (NOVA ABA)

### Visão Geral
Adicionar aba "Contracheques" ao módulo **Finance** com visualização, filtros, download e histórico.

### 1️⃣ Estrutura de Backend

**1.1 - Models** (`apps/api/app/finance/models.py`)

```python
# ADICIONAR ao arquivo existente

class Payroll(Base):
    """Folha de pagamento consolidada"""
    __tablename__ = "payrolls"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    payroll_period: Mapped[str] = mapped_column(String(7), index=True)  # "2026-08"
    company_code: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  
    # draft, processed, transmitted, paid, cancelled
    total_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_discounts: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_net: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    transmission_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transmitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    payslips: Mapped[list["Payslip"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class Payslip(Base):
    """Contracheque individual"""
    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint("payroll_id", "employee_id", name="uq_payslip_payroll_employee"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    payroll_id: Mapped[int] = mapped_column(ForeignKey("payrolls.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    employee_name: Mapped[str] = mapped_column(String(180), index=True)
    employee_document: Mapped[str] = mapped_column(String(20), index=True)
    position: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(120))
    
    # Valores
    gross_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_earnings: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # Com adicionais
    total_discounts: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    net_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    
    # Detalhes
    details: Mapped[list["PayslipDetail"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    
    # Auditoria
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # Quando viu
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PayslipDetail(Base):
    """Linhas do contracheque (proventos e descontos)"""
    __tablename__ = "payslip_details"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    payslip_id: Mapped[int] = mapped_column(ForeignKey("payslips.id", ondelete="CASCADE"), index=True)
    line_type: Mapped[str] = mapped_column(String(20), index=True)  # "earning" ou "discount"
    description: Mapped[str] = mapped_column(String(180))
    value: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference_id: Mapped[str | None] = mapped_column(String(100))  # ID externo (ESOCIAL, etc)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayrollAuditEvent(Base):
    """Auditoria de folha de pagamento"""
    __tablename__ = "payroll_audit_events"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    payroll_id: Mapped[int | None] = mapped_column(ForeignKey("payrolls.id", ondelete="SET NULL"), index=True)
    payslip_id: Mapped[int | None] = mapped_column(ForeignKey("payslips.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    # "payroll_created", "status_changed", "payslip_accessed", "payslip_downloaded"
    description: Mapped[str] = mapped_column(String(500))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**1.2 - Schemas** (`apps/api/app/finance/schemas.py` - EXPANDIR)

```python
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal

# Payslip Detail
class PayslipDetailCreate(BaseModel):
    line_type: str  # earning, discount
    description: str
    value: Decimal
    reference_id: str | None = None

class PayslipDetailResponse(PayslipDetailCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

# Payslip
class PayslipCreate(BaseModel):
    employee_id: int
    employee_name: str
    employee_document: str
    position: str
    department: str
    gross_salary: Decimal
    total_earnings: Decimal
    total_discounts: Decimal
    net_salary: Decimal
    details: list[PayslipDetailCreate]

class PayslipResponse(BaseModel):
    id: int
    employee_name: str
    employee_document: str
    position: str
    department: str
    gross_salary: Decimal
    total_earnings: Decimal
    total_discounts: Decimal
    net_salary: Decimal
    accessed_at: datetime | None
    downloaded_at: datetime | None
    details: list[PayslipDetailResponse]
    model_config = ConfigDict(from_attributes=True)

class PayslipAccessUpdate(BaseModel):
    """Para marcar como acessado"""
    accessed_at: datetime = Field(default_factory=datetime.now)

# Payroll
class PayrollCreate(BaseModel):
    payroll_period: str  # "2026-08"
    company_code: str = "universo_eletronica"
    payslips: list[PayslipCreate]

class PayrollUpdate(BaseModel):
    status: str  # draft, processed, transmitted, paid, cancelled

class PayrollResponse(BaseModel):
    id: int
    payroll_period: str
    company_code: str
    status: str
    total_gross: Decimal
    total_discounts: Decimal
    total_net: Decimal
    transmission_date: datetime | None
    created_at: datetime
    payslips: list[PayslipResponse]
    model_config = ConfigDict(from_attributes=True)

class PayrollListResponse(BaseModel):
    id: int
    payroll_period: str
    status: str
    total_gross: Decimal
    total_discounts: Decimal
    total_net: Decimal
    transmission_date: datetime | None
    payslip_count: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**1.3 - Service** (`apps/api/app/finance/service.py` - EXPANDIR)

```python
# ADICIONAR métodos ao FinanceService

async def get_payrolls(
    self,
    session: AsyncSession,
    company_code: str,
    period_start: str | None = None,
    period_end: str | None = None,
    status: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Payroll], int]:
    """Listar folhas com filtros"""
    query = select(Payroll).where(Payroll.company_code == company_code)
    
    if status:
        query = query.where(Payroll.status == status)
    if period_start:
        query = query.where(Payroll.payroll_period >= period_start)
    if period_end:
        query = query.where(Payroll.payroll_period <= period_end)
    
    # Count total
    count_query = select(func.count()).select_from(Payroll).where(
        Payroll.company_code == company_code
    )
    if status:
        count_query = count_query.where(Payroll.status == status)
    if period_start:
        count_query = count_query.where(Payroll.payroll_period >= period_start)
    if period_end:
        count_query = count_query.where(Payroll.payroll_period <= period_end)
    
    total = await session.scalar(count_query)
    
    query = query.order_by(Payroll.payroll_period.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    payrolls = result.scalars().all()
    
    return payrolls, total or 0

async def get_payslip(self, session: AsyncSession, payslip_id: int) -> Payslip | None:
    """Obter contracheque e marcar como acessado"""
    result = await session.execute(
        select(Payslip).where(Payslip.id == payslip_id)
    )
    payslip = result.scalar_one_or_none()
    
    if payslip:
        payslip.accessed_at = datetime.now(timezone.utc)
        session.add(payslip)
        await session.commit()
    
    return payslip

async def mark_payslip_downloaded(
    self, session: AsyncSession, payslip_id: int
) -> None:
    """Marcar contracheque como baixado"""
    result = await session.execute(
        select(Payslip).where(Payslip.id == payslip_id)
    )
    payslip = result.scalar_one_or_none()
    
    if payslip:
        payslip.downloaded_at = datetime.now(timezone.utc)
        session.add(payslip)
        await session.commit()

async def create_audit_event(
    self,
    session: AsyncSession,
    payroll_id: int | None,
    payslip_id: int | None,
    action: str,
    description: str,
    user_id: int,
    ip_address: str | None = None,
) -> None:
    """Registrar evento de auditoria"""
    event = PayrollAuditEvent(
        payroll_id=payroll_id,
        payslip_id=payslip_id,
        action=action,
        description=description,
        user_id=user_id,
        ip_address=ip_address,
    )
    session.add(event)
    await session.commit()
```

**1.4 - Router** (`apps/api/app/finance/router.py` - EXPANDIR)

```python
# ADICIONAR ao router de finance

@router.get("/payrolls", response_model=dict)
async def list_payrolls(
    session: AsyncSession = Depends(get_session),
    company_code: str = Query("universo_eletronica"),
    period_start: str | None = Query(None),
    period_end: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(verify_token),
) -> dict:
    """Listar folhas de pagamento com filtros"""
    payrolls, total = await service.get_payrolls(
        session,
        company_code=company_code,
        period_start=period_start,
        period_end=period_end,
        status=status,
        limit=limit,
        offset=offset,
    )
    
    # Auditoria
    await service.create_audit_event(
        session,
        payroll_id=None,
        payslip_id=None,
        action="payroll_list_accessed",
        description=f"Listagem de folhas acessada com filtros",
        user_id=current_user.id,
    )
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [PayrollListResponse.from_orm(p).model_dump() for p in payrolls],
    }

@router.get("/payrolls/{payroll_id}", response_model=PayrollResponse)
async def get_payroll(
    payroll_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(verify_token),
) -> PayrollResponse:
    """Obter detalhes da folha"""
    result = await session.execute(
        select(Payroll).where(Payroll.id == payroll_id)
    )
    payroll = result.scalar_one_or_none()
    
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")
    
    await service.create_audit_event(
        session,
        payroll_id=payroll_id,
        payslip_id=None,
        action="payroll_viewed",
        description=f"Folha {payroll.payroll_period} visualizada",
        user_id=current_user.id,
    )
    
    return PayrollResponse.from_orm(payroll)

@router.get("/payslips/{payslip_id}", response_model=PayslipResponse)
async def get_payslip(
    payslip_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(verify_token),
) -> PayslipResponse:
    """Obter contracheque individual"""
    payslip = await service.get_payslip(session, payslip_id)
    
    if not payslip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    
    await service.create_audit_event(
        session,
        payroll_id=payslip.payroll_id,
        payslip_id=payslip_id,
        action="payslip_accessed",
        description=f"Contracheque de {payslip.employee_name} acessado",
        user_id=current_user.id,
    )
    
    return PayslipResponse.from_orm(payslip)

@router.post("/payslips/{payslip_id}/download")
async def download_payslip(
    payslip_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(verify_token),
) -> dict:
    """Marcar contracheque como baixado"""
    await service.mark_payslip_downloaded(session, payslip_id)
    
    await service.create_audit_event(
        session,
        payroll_id=None,
        payslip_id=payslip_id,
        action="payslip_downloaded",
        description=f"Contracheque baixado",
        user_id=current_user.id,
    )
    
    return {"success": True, "message": "Download registrado"}

@router.get("/payroll-audit", response_model=list[dict])
async def list_payroll_audit(
    session: AsyncSession = Depends(get_session),
    payroll_id: int | None = Query(None),
    payslip_id: int | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(verify_token),
) -> list[dict]:
    """Listar auditoria de folha de pagamento"""
    query = select(PayrollAuditEvent)
    
    if payroll_id:
        query = query.where(PayrollAuditEvent.payroll_id == payroll_id)
    if payslip_id:
        query = query.where(PayrollAuditEvent.payslip_id == payslip_id)
    if action:
        query = query.where(PayrollAuditEvent.action == action)
    
    query = query.order_by(PayrollAuditEvent.created_at.desc()).limit(limit)
    result = await session.execute(query)
    events = result.scalars().all()
    
    return [
        {
            "id": e.id,
            "payroll_id": e.payroll_id,
            "payslip_id": e.payslip_id,
            "action": e.action,
            "description": e.description,
            "user_id": e.user_id,
            "ip_address": e.ip_address,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
```

### 2️⃣ Estrutura de Frontend

**2.1 - Types** (`apps/web/src/features/finance/types.ts` - EXPANDIR)

```typescript
// Contracheque Types
export interface PayslipDetail {
  id: number;
  line_type: "earning" | "discount";
  description: string;
  value: number;
  reference_id?: string;
}

export interface Payslip {
  id: number;
  employee_name: string;
  employee_document: string;
  position: string;
  department: string;
  gross_salary: number;
  total_earnings: number;
  total_discounts: number;
  net_salary: number;
  accessed_at?: string;
  downloaded_at?: string;
  details: PayslipDetail[];
}

export interface Payroll {
  id: number;
  payroll_period: string; // "2026-08"
  company_code: string;
  status: "draft" | "processed" | "transmitted" | "paid" | "cancelled";
  total_gross: number;
  total_discounts: number;
  total_net: number;
  transmission_date?: string;
  created_at: string;
  payslips: Payslip[];
}

export interface PayrollListItem {
  id: number;
  payroll_period: string;
  status: string;
  total_gross: number;
  total_discounts: number;
  total_net: number;
  transmission_date?: string;
  payslip_count: number;
  created_at: string;
}

export interface PayrollAuditEvent {
  id: number;
  payroll_id?: number;
  payslip_id?: number;
  action: string;
  description: string;
  user_id: number;
  ip_address?: string;
  created_at: string;
}
```

**2.2 - Componentes** (`apps/web/src/features/finance/components/Payroll*.tsx`)

```typescript
// PayrollList.tsx - Listagem de folhas
import React, { useState, useEffect } from "react";
import { Download, Eye, AlertCircle } from "lucide-react";

interface PayrollListProps {
  onSelectPayroll: (payroll: Payroll) => void;
}

export const PayrollList: React.FC<PayrollListProps> = ({ onSelectPayroll }) => {
  const [payrolls, setPayrolls] = useState<PayrollListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetchPayrolls();
  }, [period, status]);

  const fetchPayrolls = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (period) params.append("period_start", period);
      if (status) params.append("status", status);

      const response = await fetch(`/api/finance/payrolls?${params}`);
      const data = await response.json();
      setPayrolls(data.data);
    } catch (error) {
      console.error("Erro ao buscar folhas:", error);
    } finally {
      setLoading(false);
    }
  };

  const statusColor = (status: string) => {
    const colors: Record<string, string> = {
      draft: "bg-gray-100 text-gray-700",
      processed: "bg-blue-100 text-blue-700",
      transmitted: "bg-yellow-100 text-yellow-700",
      paid: "bg-green-100 text-green-700",
      cancelled: "bg-red-100 text-red-700",
    };
    return colors[status] || "bg-gray-100";
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-4 mb-4">
        <input
          type="month"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="px-3 py-2 border rounded"
          placeholder="Período"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="px-3 py-2 border rounded"
        >
          <option value="">Todos os status</option>
          <option value="draft">Rascunho</option>
          <option value="processed">Processada</option>
          <option value="transmitted">Transmitida</option>
          <option value="paid">Paga</option>
          <option value="cancelled">Cancelada</option>
        </select>
      </div>

      {loading ? (
        <p className="text-center py-8">Carregando...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3">Período</th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Total Bruto</th>
                <th className="text-right p-3">Descontos</th>
                <th className="text-right p-3">Líquido</th>
                <th className="text-center p-3">Funcionários</th>
                <th className="text-center p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {payrolls.map((payroll) => (
                <tr key={payroll.id} className="border-b hover:bg-gray-50">
                  <td className="p-3 font-mono">{payroll.payroll_period}</td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-sm ${statusColor(payroll.status)}`}>
                      {payroll.status}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    R$ {payroll.total_gross.toFixed(2)}
                  </td>
                  <td className="p-3 text-right">
                    R$ {payroll.total_discounts.toFixed(2)}
                  </td>
                  <td className="p-3 text-right font-semibold">
                    R$ {payroll.total_net.toFixed(2)}
                  </td>
                  <td className="p-3 text-center">{payroll.payslip_count}</td>
                  <td className="p-3 text-center">
                    <button
                      onClick={() => onSelectPayroll(payroll as any)}
                      className="text-blue-600 hover:text-blue-800"
                      title="Visualizar"
                    >
                      <Eye size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// PayslipDetail.tsx - Detalhes do contracheque
export const PayslipDetail: React.FC<{ payslip: Payslip }> = ({ payslip }) => {
  const handleDownload = async () => {
    try {
      await fetch(`/api/finance/payslips/${payslip.id}/download`, {
        method: "POST",
      });
      // Implementar download de PDF
      window.open(`/api/finance/payslips/${payslip.id}/pdf`);
    } catch (error) {
      console.error("Erro ao baixar:", error);
    }
  };

  const earnings = payslip.details.filter((d) => d.line_type === "earning");
  const discounts = payslip.details.filter((d) => d.line_type === "discount");

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start border-b pb-4">
        <div>
          <h2 className="text-lg font-bold">{payslip.employee_name}</h2>
          <p className="text-gray-600 text-sm">{payslip.position}</p>
          <p className="text-gray-500 text-xs">CPF: {payslip.employee_document}</p>
        </div>
        <button
          onClick={handleDownload}
          className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
        >
          <Download size={18} />
          Baixar PDF
        </button>
      </div>

      {/* Proventos */}
      <div>
        <h3 className="font-bold mb-3">Proventos</h3>
        <div className="space-y-2">
          {earnings.map((detail) => (
            <div key={detail.id} className="flex justify-between text-sm">
              <span>{detail.description}</span>
              <span className="text-green-600 font-mono">
                R$ {detail.value.toFixed(2)}
              </span>
            </div>
          ))}
          <div className="flex justify-between font-semibold border-t pt-2">
            <span>Total Proventos</span>
            <span className="text-green-600">R$ {payslip.total_earnings.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Descontos */}
      <div>
        <h3 className="font-bold mb-3">Descontos</h3>
        <div className="space-y-2">
          {discounts.map((detail) => (
            <div key={detail.id} className="flex justify-between text-sm">
              <span>{detail.description}</span>
              <span className="text-red-600 font-mono">
                - R$ {detail.value.toFixed(2)}
              </span>
            </div>
          ))}
          <div className="flex justify-between font-semibold border-t pt-2">
            <span>Total Descontos</span>
            <span className="text-red-600">- R$ {payslip.total_discounts.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Resumo */}
      <div className="bg-gray-50 p-4 rounded space-y-2">
        <div className="flex justify-between">
          <span>Salário Base</span>
          <span className="font-mono">R$ {payslip.gross_salary.toFixed(2)}</span>
        </div>
        <div className="flex justify-between text-lg font-bold border-t pt-2">
          <span>Líquido</span>
          <span className="text-green-700">R$ {payslip.net_salary.toFixed(2)}</span>
        </div>
      </div>

      {/* Auditoria */}
      <div className="text-xs text-gray-500 space-y-1 border-t pt-2">
        {payslip.accessed_at && (
          <p>Último acesso: {new Date(payslip.accessed_at).toLocaleString("pt-BR")}</p>
        )}
        {payslip.downloaded_at && (
          <p>Último download: {new Date(payslip.downloaded_at).toLocaleString("pt-BR")}</p>
        )}
      </div>
    </div>
  );
};
```

**2.3 - Feature Tab** (`apps/web/src/features/finance/PayrollTab.tsx`)

```typescript
import React, { useState } from "react";
import { Tabs } from "lucide-react";
import { PayrollList } from "./components/PayrollList";
import { PayslipDetail } from "./components/PayslipDetail";
import { Payroll } from "./types";

export const PayrollTab: React.FC = () => {
  const [selectedPayroll, setSelectedPayroll] = useState<Payroll | null>(null);
  const [selectedPayslip, setSelectedPayslip] = useState<number | null>(null);

  if (selectedPayslip) {
    const payslip = selectedPayroll?.payslips.find((p) => p.id === selectedPayslip);
    if (payslip) {
      return (
        <div className="space-y-4">
          <button
            onClick={() => setSelectedPayslip(null)}
            className="text-blue-600 hover:text-blue-800"
          >
            ← Voltar
          </button>
          <PayslipDetail payslip={payslip} />
        </div>
      );
    }
  }

  if (selectedPayroll) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => setSelectedPayroll(null)}
          className="text-blue-600 hover:text-blue-800"
        >
          ← Voltar
        </button>
        <div className="grid gap-4">
          {selectedPayroll.payslips.map((payslip) => (
            <div
              key={payslip.id}
              onClick={() => setSelectedPayslip(payslip.id)}
              className="p-4 border rounded cursor-pointer hover:bg-gray-50"
            >
              <div className="flex justify-between">
                <div>
                  <p className="font-bold">{payslip.employee_name}</p>
                  <p className="text-sm text-gray-600">{payslip.position}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono font-semibold">
                    R$ {payslip.net_salary.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return <PayrollList onSelectPayroll={setSelectedPayroll} />;
};
```

**2.4 - Integração** (`apps/web/src/features/finance/FinanceDashboard.tsx` - MODIFICAR)

```typescript
// No componente principal, adicionar aba:

<div className="space-y-4">
  <div className="flex gap-4 border-b">
    <button
      onClick={() => setActiveTab("entries")}
      className={activeTab === "entries" ? "border-b-2 border-blue-600 pb-2" : "pb-2"}
    >
      Lançamentos
    </button>
    <button
      onClick={() => setActiveTab("accounts")}
      className={activeTab === "accounts" ? "border-b-2 border-blue-600 pb-2" : "pb-2"}
    >
      Contas
    </button>
    {/* NOVO */}
    <button
      onClick={() => setActiveTab("payroll")}
      className={activeTab === "payroll" ? "border-b-2 border-blue-600 pb-2" : "pb-2"}
    >
      Contracheques
    </button>
  </div>

  {activeTab === "entries" && <FinancialEntries />}
  {activeTab === "accounts" && <FinancialAccounts />}
  {/* NOVO */}
  {activeTab === "payroll" && <PayrollTab />}
</div>
```

---

## 📊 CHECKLIST DE IMPLEMENTAÇÃO

### Fase 0 - Preparação
- [ ] Criar migration para tabelas de folha
- [ ] Revisar models (Payroll, Payslip, PayslipDetail, PayrollAuditEvent)
- [ ] Validar schemas Pydantic
- [ ] Criar seed data (dados de teste)

### Fase 1 - Backend (2-3 dias)
- [ ] Implementar models.py
- [ ] Implementar schemas.py
- [ ] Implementar service.py (métodos)
- [ ] Implementar router.py (endpoints)
- [ ] Testes unitários (pytest)
- [ ] Validação de endpoint /docs

### Fase 2 - Frontend (2-3 dias)
- [ ] Adicionar types.ts
- [ ] Criar PayrollList.tsx
- [ ] Criar PayslipDetail.tsx
- [ ] Criar PayrollTab.tsx
- [ ] Integração em FinanceDashboard.tsx
- [ ] Estilos em finance.css
- [ ] Testes de navegação

### Fase 3 - PDF & Download (1-2 dias)
- [ ] Implementar geração de PDF em Python (ReportLab)
- [ ] Endpoint GET /finance/payslips/{id}/pdf
- [ ] Download no frontend
- [ ] Marca automaticamente como downloaded

### Fase 4 - Auditoria & Relatórios (1 dia)
- [ ] Página /finance/payroll-audit (com filtros)
- [ ] Relatório de acesso
- [ ] Relatório de downloads
- [ ] Dashboard de folhas processadas

### Fase 5 - Testes & Qualidade
- [ ] pytest coverage > 80%
- [ ] tsc sem erros
- [ ] Ruff clean
- [ ] Vitest coverage > 60%
- [ ] Teste end-to-end

---

## 🎯 ROADMAP GERAL (PRIORIZADO)

### SPRINT 1 (Semana de 17/08)
1. ✅ **Laboratório Layout** (full-width, filtros)
2. ✅ **Filtro Período** (fix opened_at)
3. ⬜ **Contracheques Backend** (models + endpoints)

### SPRINT 2 (Semana de 24/08)
1. ⬜ **Contracheques Frontend** (componentes)
2. ⬜ **KPIs Dinâmicos** (laboratório)
3. ⬜ **Auditoria Laboratório** (histórico)

### SPRINT 3 (Semana de 31/08)
1. ⬜ **PDF Geração** (contracheque)
2. ⬜ **Gráficos Interativos** (laboratório)
3. ⬜ **Alertas Automáticos** (laboratório)

### SPRINT 4 (Semana de 07/09)
1. ⬜ **Testes** (pytest + vitest)
2. ⬜ **Comercial Phase A** (preparação)
3. ⬜ **Performance** (índices, queries)

---

## 🔒 SEGURANÇA & COMPLIANCE

### Contracheques - Considerações
- ✅ Cada funcionário vê apenas seu contracheque
- ✅ Auditoria de acesso (quem, quando)
- ✅ Auditoria de download
- ✅ Histórico de alterações
- ✅ IP registrado nos eventos
- ⚠️ Criptografia de transferência (HTTPS obrigatório)
- ⚠️ Considerar criptografia em repouso para dados sensíveis

### Permissões Recomendadas
```python
- "payroll.view_all" → Administrativo/RH
- "payroll.view_own" → Funcionário (vê seu próprio)
- "payroll.create" → RH/Administrativo
- "payroll.transmit" → RH/Administrativo
- "payroll_audit.view" → Compliance/Auditoria
```

---

## 📚 PRÓXIMAS FASES (APÓS CONTRACHEQUES)

### Fase Comercial
- Integração com CRM
- Pipeline visual
- Forecast automático

### Fase Estoque
- Movimentação de itens
- Alertas de baixo estoque
- Relatórios de saída

### Fase Integrações
- ESOCIAL (folha)
- EFD-Reinf (contribuições)
- API de terceiros

---

## 📝 NOTAS FINAIS

1. **Código Atual**: Bem estruturado, SDD implementado corretamente
2. **Prioridades**: Laboratório UI → Contracheques → Comercial
3. **Qualidade**: Manter padrões de Type Safety + Auditoria
4. **Performance**: Adicionar índices conforme necessidade
5. **Documentação**: Manter OpenAPI atualizada

**Próximo passo**: Confirme a ordem de execução e vamos começar pela **Fase A do Laboratório** ou direto pelos **Contracheques**?
