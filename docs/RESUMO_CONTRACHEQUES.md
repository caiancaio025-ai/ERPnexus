# 📋 CONTRACHEQUES - RESUMO EXECUTIVO

## 🎯 Objetivo
Implementar um módulo completo de gestão de contracheques no sistema NEXUS com visualização, auditoria e download de PDF.

---

## 📊 ARQUITETURA DE DADOS

### Diagrama ER (Entity Relationship)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          SISTEMA DE FOLHA                           │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                         PAYROLLS (Folhas)                            │
├──────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ payroll_period ────────┐  (Único período por empresa)               │
│ company_code           │                                             │
│ status                 │  (draft → processed → transmitted → paid)   │
│ total_gross ─────────┐ │                                             │
│ total_discounts       └─┼─ Cálculos de roll-up                       │
│ total_net ────────────┐ │  (from payslips)                           │
│ transmission_date      │                                             │
│ transmitted_by (FK)    │                                             │
│ created_by (FK) ───────┼─→ users                                    │
│ created_at             │                                             │
│ updated_at             │                                             │
└──────────────────────────────────────────────────────────────────────┘
            │
            │ 1:N
            ↓
┌──────────────────────────────────────────────────────────────────────┐
│                      PAYSLIPS (Contracheques)                        │
├──────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ payroll_id (FK) ──────→ payrolls                                    │
│ employee_id (FK) ─────→ users                                       │
│ employee_name          (Snapshot no momento)                         │
│ employee_document                                                    │
│ position                                                             │
│ department                                                           │
│ gross_salary ──────────┐                                             │
│ total_earnings         ├─ Cálculos (from payslip_details)           │
│ total_discounts        │                                             │
│ net_salary ────────────┘                                             │
│ accessed_at ────────────→ Auditoria: quando visualizado             │
│ downloaded_at ─────────→ Auditoria: quando baixado                  │
│ created_at             │                                             │
│ updated_at             │                                             │
└──────────────────────────────────────────────────────────────────────┘
            │
            │ 1:N
            ↓
┌──────────────────────────────────────────────────────────────────────┐
│               PAYSLIP_DETAILS (Linhas do Contracheque)              │
├──────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ payslip_id (FK) ──────→ payslips                                    │
│ line_type             (earning ou discount)                         │
│ description           (ex: "Salário Base", "INSS", "FGTS")         │
│ value                                                                │
│ reference_id          (ID externo: ESOCIAL, etc)                   │
│ created_at                                                           │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│            PAYROLL_AUDIT_EVENTS (Auditoria de Folha)               │
├──────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                              │
│ payroll_id (FK)       (Qual folha? Null se ação geral)             │
│ payslip_id (FK)       (Qual contracheque? Null se folha inteira)   │
│ action                (payroll_created, payslip_accessed, ...)     │
│ description           (Descrição legível)                           │
│ user_id (FK) ────────→ users (Quem fez?)                           │
│ ip_address            (De onde?)                                    │
│ created_at            (Quando?)                                     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 FLUXO DE DADOS

### 1️⃣ Entrada (Criação de Folha)

```
Usuário RH seleciona período (Agosto/2026)
         │
         ↓
    Sistema busca:
    ├─ Funcionários ativos
    ├─ Salário base de cada um
    ├─ Adicionais (hora extra, bônus)
    └─ Descontos (INSS, IR, etc)
         │
         ↓
    Cria PAYROLL (status: draft)
         │
    Para cada funcionário:
         ├─ Cria PAYSLIP
         ├─ Calcula proventos (payslip_details type=earning)
         ├─ Calcula descontos (payslip_details type=discount)
         └─ Roll-up: payslip.total_*
         │
         ↓
    Roll-up de PAYROLL: total_gross, total_discounts, total_net
         │
         ↓
    Registra: payroll_audit_events (action: payroll_created)
         │
         ↓
    ✅ Folha salva em estado "draft"
```

### 2️⃣ Processamento (Status Workflow)

```
DRAFT (Rascunho)
  ├─ Edições permitidas
  ├─ Funcionários veem? Não
  └─ Ações: Processar, Cancelar
      │
      ↓
PROCESSED (Processada)
  ├─ Validações completadas
  ├─ Cálculos confirmados
  ├─ Funcionários veem? Opcional
  └─ Ações: Transmitir, Voltar, Cancelar
      │
      ↓
TRANSMITTED (Transmitida)
  ├─ Enviada ao ESOCIAL/eSocial
  ├─ Integração com governo
  ├─ Funcionários veem? Sim
  └─ Ações: Confirmar pagamento, Cancelar (com caution)
      │
      ↓
PAID (Paga)
  ├─ Transferência bancária realizada
  ├─ Funcionários veem? Sim (histórico)
  └─ Ações: Nenhuma (somente leitura)
```

### 3️⃣ Visualização por Funcionário

```
Funcionário acessa: /finance/payroll/my-payslips
         │
         ↓
    Sistema verifica permissão:
    ├─ Pode ver apenas seus contracheques
    ├─ Status deve ser TRANSMITTED ou PAID
    └─ Auditoria: registra accessed_at
         │
         ↓
    Mostra contracheque com:
    ├─ Dados pessoais (nome, CPF, cargo)
    ├─ Período da folha
    ├─ Proventos (tabela)
    ├─ Descontos (tabela)
    ├─ Líquido a receber (destaque)
    ├─ Botão "Baixar PDF"
    └─ Data de acesso/último download
         │
         ↓
    Se clica "Baixar PDF":
    ├─ Sistema registra: downloaded_at
    ├─ Auditoria: payslip_downloaded
    ├─ PDF gerado (ReportLab)
    └─ Cliente baixa PDF
```

### 4️⃣ Auditoria & Compliance

```
Cada ação registra:
┌──────────────────────────────────┐
│ Quem?      → user_id (FK users)  │
│ Quando?    → created_at          │
│ O quê?     → action + description│
│ De onde?   → ip_address          │
│ Contexto?  → payroll/payslip id  │
└──────────────────────────────────┘

Ações auditadas:
- payroll_created          (Folha criada)
- payroll_status_changed   (Status mudou)
- payslip_accessed         (Contracheque visualizado)
- payslip_downloaded       (PDF baixado)
- payroll_transmitted      (Enviada ao governo)
- payroll_cancelled        (Cancelada)

Visualização da auditoria:
RH acessa: /finance/payroll-audit
├─ Filtrar por período
├─ Filtrar por ação
├─ Filtrar por usuário
├─ Relatório: "Quem baixou o quê, quando"
└─ Relatório: "Alterações na folha"
```

---

## 🛠️ STACK TÉCNICO

### Backend
```python
Framework: FastAPI
ORM: SQLAlchemy 2.0
Database: PostgreSQL
PDF: ReportLab
Validation: Pydantic v2
Auth: JWT + Argon2
Async: asyncio + asyncpg
```

### Frontend
```typescript
Framework: React 19
State: React Hooks
Routing: React Router v7
HTTP: fetch API
Type Safety: TypeScript strict
Icons: Lucide React
```

### Database
```sql
PostgreSQL 13+
Alembic (migrations)
Connection pooling: psycopg[binary]
Indexes: optimizados para filtros
```

---

## 📈 CARGA & PERFORMANCE

### Estimativas de Volume

```
Empresa: Universo Eletrônica
Funcionários: ~50
Períodos armazenados: ~24 (2 anos)

Total de registros:
├─ payrolls: 24 (2 anos)
├─ payslips: 24 × 50 = 1.200
├─ payslip_details: 1.200 × 8 (média linhas) = 9.600
└─ payroll_audit_events: ~10.000 (estimado)

Tamanho estimado: ~50 MB (incluindo índices)
```

### Query Performance

```
Listar folhas (filtrado):
  SELECT * FROM payrolls 
  WHERE payroll_period >= ? AND status = ?
  ORDER BY payroll_period DESC
  LIMIT 25
  
  Índices: (payroll_period, status)
  Tempo: < 50ms

Visualizar contracheque:
  SELECT p.*, pd.* FROM payslips p
  LEFT JOIN payslip_details pd ON p.id = pd.payslip_id
  WHERE p.id = ? AND p.employee_id = ?
  
  Índices: (id), (employee_id)
  Tempo: < 20ms

Auditoria:
  SELECT * FROM payroll_audit_events
  WHERE created_at > ? ORDER BY created_at DESC
  
  Índices: (created_at), (action)
  Tempo: < 100ms
```

---

## 🔐 SEGURANÇA

### Permissões

```python
PAYROLL_PERMISSIONS = {
    "admin": ["view_all", "create", "edit", "transmit", "audit"],
    "rh": ["view_all", "create", "edit", "transmit"],
    "manager": ["view_team"],
    "employee": ["view_own"],
    "finance": ["view_all", "audit"],
}
```

### Validações

```
1. Funcionário pode ver apenas seu contracheque:
   SELECT * FROM payslips WHERE employee_id = current_user.id

2. RH pode ver todos:
   SELECT * FROM payslips WHERE company_code = current_company

3. Não pode editar folha já transmitida:
   if payroll.status == "transmitted":
       raise PermissionError("Cannot edit transmitted payroll")

4. Transições de status permitidas:
   draft → processed, cancelled
   processed → transmitted, draft, cancelled
   transmitted → paid, cancelled (com auditoria especial)
   paid → readonly
```

### Dados Sensíveis

```
Proteger:
├─ CPF (máscara: ***.***.***-**)
├─ Salário (acesso restrito)
├─ Histórico (apenas RH + Auditoria)
└─ IPs na auditoria (geolocalização?)

HTTPS obrigatório (environment: production)
Senha forte obrigatória (8+ chars, números, símbolos)
2FA recomendado para RH
Rate limiting: 10 requisições/minuto por usuário
```

---

## 📝 MIGRATION CHECKLIST

### Fase 0 - Preparação (1 dia)
- [ ] Backup do banco de dados
- [ ] Testar migration em ambiente staging
- [ ] Preparar dados de teste
- [ ] Validar modelos SQL
- [ ] Code review do SQL

### Fase 1 - Criação de Tabelas (1 dia)
```bash
cd apps/api
alembic revision --autogenerate -m "Add payroll tables"
# Editar o arquivo gerado
alembic upgrade head
# Verificar criação
psql -c "\dt payroll*"  # Verificar tabelas
```

### Fase 2 - Backend Models (2 dias)
- [ ] Implementar models.py (Payroll, Payslip, etc)
- [ ] Implementar schemas.py (Pydantic)
- [ ] Implementar service.py (business logic)
- [ ] Implementar router.py (endpoints)
- [ ] Testes unitários

### Fase 3 - Frontend Components (2 dias)
- [ ] types.ts
- [ ] PayrollList.tsx
- [ ] PayslipDetail.tsx
- [ ] PayrollTab.tsx
- [ ] Integração em FinanceDashboard.tsx

### Fase 4 - PDF & Download (1 dia)
- [ ] ReportLab setup
- [ ] Gerador de PDF
- [ ] Endpoint de download
- [ ] Teste de PDF

### Fase 5 - Testes & QA (1 dia)
- [ ] pytest coverage
- [ ] vitest coverage
- [ ] E2E tests
- [ ] Performance tests

---

## 🚀 DEPLOY & ROLLOUT

### Ambiente

```
1. Desenvolvimento: local
   ├─ seed data test
   └─ testes automáticos

2. Staging: produção-like
   ├─ dados de teste completos
   ├─ testes de carga
   └─ validação de RH

3. Produção: real
   ├─ dados reais do mês
   ├─ rollout em fases
   └─ monitoramento 24h
```

### Strategy de Rollout

```
Fase 1: RH testa com dados de agosto
        ├─ Criar folha
        ├─ Validar cálculos
        └─ Transmitir para ESOCIAL (sandbox)

Fase 2: Teste com funcionários
        ├─ Grupo piloto (~5 pessoas)
        ├─ Feedback
        └─ Ajustes

Fase 3: Deploy completo
        ├─ Toda empresa
        ├─ Suporte 24h
        └─ Monitoramento
```

### Rollback Plan

```
Se problema:
1. Desabilitar acesso a contracheques
   └─ Feature flag: PAYROLL_ENABLED = false

2. Manter dados (não deletar)
   └─ Auditoria intacta

3. Reverter migration
   └─ alembic downgrade -1

4. Comunicar usuários
   └─ Email sobre indisponibilidade
```

---

## 📊 MÉTRICAS & MONITORING

### KPIs de Uso

```
- Folhas criadas por mês
- Contracheques visualizados (%)
- Contracheques baixados (%)
- Tempo médio de download (ms)
- Erros de geração de PDF
- Auditoria: acessos por dia
```

### Alertas

```
Dispara alerta se:
- PDF falha 2+ vezes em 1 hora
- Contracheque tarda > 5 segundos
- Auditoria não registra em 2 min
- Storage fica < 10% disponível
- Downloads > 1000/hora (ataque?)
```

### Logs

```
Tudo em:
1. Application logs
   └─ ERROR, WARNING, INFO

2. Audit logs
   └─ payroll_audit_events (sempre)

3. Access logs
   └─ Nginx/Caddy (quem acessou quando)

4. Error tracking
   └─ Sentry ou similar
```

---

## 💡 MELHORIAS FUTURAS

### Fase 2 (Próximo Quarter)
- [ ] Integração ESOCIAL automática
- [ ] Gerar DARF/guia de impostos
- [ ] Dashboard de RH (análises)
- [ ] Exportar para Excel/CSV
- [ ] Integração com banco (via API)

### Fase 3 (Future)
- [ ] Machine learning (detecção de anomalias)
- [ ] App mobile (contracheque no celular)
- [ ] WhatsApp bot (avisar quando disponível)
- [ ] Assinatura digital
- [ ] Certificado digital

---

## 📞 SUPORTE & CONTATO

### Dúvidas sobre:
- **Modelos**: Ver `apps/api/app/finance/models.py`
- **APIs**: Ver `/docs` (FastAPI Swagger)
- **Frontend**: Ver componentes em `apps/web/src/features/finance/`
- **Migrations**: Ver `apps/api/alembic/versions/`
- **Auditoria**: `payroll_audit_events` table + logs

### Testes
```bash
# Backend
pytest apps/api/tests/test_payroll.py -v

# Frontend
npm test -- PayrollList.test.tsx

# Integration
pytest tests/e2e/test_payroll_flow.py
```

### Documentação
- OpenAPI: `http://localhost:8000/docs`
- ADRs: `docs/architecture/`
- Database: `MIGRATION_CONTRACHEQUES.sql`

---

**Status**: ✅ Pronto para implementação  
**Prioridade**: Alta  
**Estimativa**: 5-6 dias de desenvolvimento  
**Revisão**: QA + RH + Auditoria  

---

*Última atualização: 17/08/2026*
