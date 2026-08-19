# 🔗 INTEGRAÇÃO: PAYROLL + EMPLOYEES + DOCUMENTS

Quando um **Contracheque** é gerado, ele automaticamente vira um **EmployeeDocument** que:
- ✅ Funcionário consegue baixar
- ✅ Fica versionado por período (2026-08, 2026-09, etc)
- ✅ Registra acesso e downloads na auditoria
- ✅ Pode expirar automaticamente

---

## 📊 FLUXO DE DADOS

```
1. RH cria PAYROLL (Agosto/2026)
   ↓
2. Sistema cria PAYSLIPS (um por funcionário)
   ├─ Valida dados
   ├─ Calcula proventos e descontos
   ├─ Roll-up de totais
   ↓
3. Gera PDF (ReportLab)
   ├─ HTML → PDF profissional
   ├─ Salva em /storage/payslips/{employee_id}/2026-08/
   ↓
4. Cria EmployeeDocument automaticamente
   ├─ Type: "contracheque"
   ├─ Period: "2026-08"
   ├─ is_public: TRUE (funcionário vê)
   ├─ Version: 1
   ↓
5. Funcionário acessa /employees/me/documents
   ├─ Vê "Contracheque Agosto/2026"
   ├─ Clica em baixar
   ├─ Auditoria registra: documento_acessado + documento_baixado
```

---

## 🔧 IMPLEMENTAÇÃO

### Backend: Modificar Finance Router

```python
# apps/api/app/finance/router.py

@router.post("/payrolls/{payroll_id}/generate-pdf", status_code=201)
async def generate_and_save_payroll_pdf(
    payroll_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(verify_token),
) -> dict:
    """
    Gerar PDF de contracheques e salvar como EmployeeDocuments
    
    Para cada payslip:
    1. Gera PDF individual
    2. Salva em /storage/payslips/
    3. Cria EmployeeDocument com tipo="contracheque"
    """
    
    # 1. Buscar payroll e payslips
    payroll = await session.get(Payroll, payroll_id)
    if not payroll:
        raise HTTPException(status_code=404, detail="Payroll not found")
    
    # 2. Verificar permissão (deve ser RH)
    
    # 3. Para cada payslip, gerar PDF
    from app.finance.quote_pdf import generate_payslip_pdf  # Usar ReportLab
    
    generated_count = 0
    for payslip in payroll.payslips:
        try:
            # Gerar PDF
            pdf_bytes = await generate_payslip_pdf(payslip)
            
            # Salvar em disco
            storage_dir = Path(f"/storage/payslips/{payslip.employee_id}")
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            file_name = f"contracheque_{payroll.payroll_period}_{payslip.id}.pdf"
            file_path = str(storage_dir / file_name)
            
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(pdf_bytes)
            
            # Calcular checksum
            checksum = hashlib.sha256(pdf_bytes).hexdigest()
            
            # 4. Criar EmployeeDocument
            doc = await EmployeeService.create_document(
                session,
                employee_id=payslip.employee_id,
                document_type="contracheque",
                file_name=file_name,
                file_path=file_path,
                mime_type="application/pdf",
                file_size=len(pdf_bytes),
                checksum=checksum,
                user_id=current_user.id,
                is_public=True,  # Funcionário vê
                metadata_period=payroll.payroll_period,  # "2026-08"
                expiration_date=None,  # Contracheques não expiram
            )
            
            generated_count += 1
            
        except Exception as e:
            print(f"Erro ao gerar PDF para payslip {payslip.id}: {e}")
            continue
    
    # 5. Registrar auditoria
    await EmployeeService.create_audit_event(
        session,
        action="payroll_pdf_generated",
        description=f"PDFs gerados para {generated_count} contracheques ({payroll.payroll_period})",
        user_id=current_user.id,
    )
    
    return {
        "success": True,
        "payroll_id": payroll_id,
        "generated_count": generated_count,
        "total_payslips": len(payroll.payslips),
    }
```

### PDF Generation (apps/api/app/finance/payslip_pdf.py - NOVO)

```python
"""
Gerador de PDF de Contracheque
apps/api/app/finance/payslip_pdf.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
from decimal import Decimal

from app.employees.models import Employee
from app.finance.models import Payslip


async def generate_payslip_pdf(payslip: Payslip) -> bytes:
    """
    Gerar PDF profissional do contracheque
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    story = []
    styles = getSampleStyleSheet()
    
    # ========================================================================
    # Cabeçalho
    # ========================================================================
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor("#003366"),
        spaceAfter=12,
        alignment=1,  # Center
    )
    
    story.append(Paragraph("CONTRACHEQUE", title_style))
    story.append(Paragraph(f"Período: {payslip.payroll.payroll_period}", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # ========================================================================
    # Dados do Funcionário
    # ========================================================================
    
    employee_data = [
        ["NOME", payslip.employee_name],
        ["CPF", payslip.employee_document],
        ["CARGO", payslip.position],
        ["DEPARTAMENTO", payslip.department],
    ]
    
    employee_table = Table(employee_data, colWidths=[3*cm, 12*cm])
    employee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F0F0F0")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(employee_table)
    story.append(Spacer(1, 0.5*cm))
    
    # ========================================================================
    # Proventos
    # ========================================================================
    
    story.append(Paragraph("<b>PROVENTOS</b>", styles['Heading2']))
    
    earnings_data = [["DESCRIÇÃO", "VALOR"]]
    for detail in payslip.details:
        if detail.line_type == "earning":
            earnings_data.append([
                detail.description,
                f"R$ {detail.value:,.2f}",
            ])
    
    # Total de proventos
    earnings_data.append([
        "TOTAL PROVENTOS",
        f"R$ {payslip.total_earnings:,.2f}",
    ])
    
    earnings_table = Table(earnings_data, colWidths=[10*cm, 5*cm])
    earnings_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E8F0F8")),
    ]))
    
    story.append(earnings_table)
    story.append(Spacer(1, 0.3*cm))
    
    # ========================================================================
    # Descontos
    # ========================================================================
    
    story.append(Paragraph("<b>DESCONTOS</b>", styles['Heading2']))
    
    discounts_data = [["DESCRIÇÃO", "VALOR"]]
    for detail in payslip.details:
        if detail.line_type == "discount":
            discounts_data.append([
                detail.description,
                f"R$ {detail.value:,.2f}",
            ])
    
    # Total de descontos
    discounts_data.append([
        "TOTAL DESCONTOS",
        f"R$ {payslip.total_discounts:,.2f}",
    ])
    
    discounts_table = Table(discounts_data, colWidths=[10*cm, 5*cm])
    discounts_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#663333")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F8E8E8")),
    ]))
    
    story.append(discounts_table)
    story.append(Spacer(1, 0.5*cm))
    
    # ========================================================================
    # Resumo Final
    # ========================================================================
    
    summary_data = [
        ["SALÁRIO BASE", f"R$ {payslip.gross_salary:,.2f}"],
        ["TOTAL PROVENTOS", f"R$ {payslip.total_earnings:,.2f}"],
        ["TOTAL DESCONTOS", f"R$ {payslip.total_discounts:,.2f}"],
        ["LÍQUIDO A RECEBER", f"R$ {payslip.net_salary:,.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[10*cm, 5*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -2), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#003366")),
        ('TEXTCOLOR', (0, 0), (-1, -2), colors.black),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -2), 11),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 1*cm))
    
    # ========================================================================
    # Rodapé
    # ========================================================================
    
    footer_text = f"""
    <font size=8>
    Comprovante de pagamento gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}<br/>
    Universo Eletrônica - Todos os direitos reservados
    </font>
    """
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # ========================================================================
    # Gerar PDF
    # ========================================================================
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
```

---

## 🎯 FLUXO COMPLETO (Cronograma)

### Dia 1: Módulo EMPLOYEES
- ✅ Migration criar tabelas
- ✅ Models: Employee, EmployeeDocument, EmployeeAuditEvent
- ✅ Service + Router
- ✅ Frontend: EmployeeForm, EmployeeList
- ✅ Testes

### Dia 2: Módulo DOCUMENTS
- ✅ Upload de arquivos
- ✅ Listagem
- ✅ Download com auditoria
- ✅ Frontend: DocumentUpload, EmployeeDocuments

### Dia 3: Integração PAYROLL
- ✅ Modificar Payslip models (add employee_id FK)
- ✅ Gerar PDF (ReportLab)
- ✅ Auto-salvar em EmployeeDocument
- ✅ Endpoint: POST /finance/payrolls/{id}/generate-pdf

### Dia 4: Frontend Funcionário
- ✅ Aba "Meus Documentos" (/employees/me/documents)
- ✅ Baixar contracheque próprio
- ✅ Auditoria de visualização

### Dia 5: QA + Polish
- ✅ Testes end-to-end
- ✅ Performance
- ✅ Segurança (permissões)
- ✅ UX/CSS

---

## 🔒 SEGURANÇA

### Permissões Necessárias

```python
PERMISSIONS = {
    "admin": {
        "employees": ["create", "read", "update", "terminate"],
        "documents": ["upload", "delete", "view_all"],
        "payroll": ["create", "generate_pdf"],
    },
    "rh": {
        "employees": ["create", "read", "update", "terminate"],
        "documents": ["upload", "delete"],
        "payroll": ["create", "generate_pdf"],
    },
    "manager": {
        "employees": ["read"],
        "documents": ["view_team"],
    },
    "employee": {
        "documents": ["view_own", "download_own"],
        "profile": ["view_own", "update_own"],
    },
}
```

### Validações

```python
# Funcionário só vê seu contracheque
if current_user.id != payslip.employee_id:
    raise PermissionError("Cannot access other employee's document")

# RH vê tudo
if has_permission(current_user, "documents.view_all"):
    # OK
```

---

## 📋 CHECKLIST

### Backend
- [ ] Migration 004_add_employees_tables.py
- [ ] Models: Employee, EmployeeDocument, EmployeeAuditEvent
- [ ] Schemas Pydantic completos
- [ ] Service com métodos CRUD
- [ ] Router com 12+ endpoints
- [ ] Integração Payroll → Documents
- [ ] PDF generation (ReportLab)
- [ ] Testes unitários

### Frontend
- [ ] Types TypeScript
- [ ] EmployeeForm component
- [ ] EmployeeList component
- [ ] DocumentUpload component
- [ ] EmployeeDocuments component
- [ ] MyDocuments page
- [ ] CSS estilos
- [ ] Testes vitest

### Database
- [ ] Tabelas criadas
- [ ] Índices presentes
- [ ] Foreign keys OK
- [ ] Dados de teste

### Auditoria
- [ ] Eventos registrados
- [ ] Acesso rastreado
- [ ] Download rastreado
- [ ] Relatório de auditoria

---

## 🚀 DEPLOY

### Staging
```bash
# 1. Backup
pg_dump nexus_db > backup_2026-08-17.sql

# 2. Migration
cd apps/api
alembic upgrade head

# 3. Seed data
python scripts/create_test_employees.py

# 4. Testes
pytest tests/test_employees.py -v
npm test -- Employee

# 5. Validar
curl http://localhost:8000/api/employees -H "Authorization: Bearer $TOKEN"
```

### Produção
```bash
# 1. Backup COMPLETO
# 2. Aplicar migration
# 3. Rollout gradual (10% → 50% → 100%)
# 4. Monitoramento 24h
# 5. Rollback plan pronto
```

---

**Próxima etapa**: Você quer que eu crie os arquivos frontend de verdade? 🚀

*Último passo antes de colar tudo no projeto!*
