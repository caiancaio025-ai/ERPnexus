-- Migration: Adicionar suporte a Contracheques
-- Data: 2026-08-17
-- Arquivo: alembic/versions/002_add_payroll.py

-- ============================================================================
-- Tabela: payrolls (Folhas de Pagamento Consolidadas)
-- ============================================================================

CREATE TABLE IF NOT EXISTS payrolls (
    id SERIAL PRIMARY KEY,
    payroll_period VARCHAR(7) NOT NULL,  -- Formato: "2026-08"
    company_code VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    
    -- Valores consolidados
    total_gross NUMERIC(14, 2) DEFAULT 0,
    total_discounts NUMERIC(14, 2) DEFAULT 0,
    total_net NUMERIC(14, 2) DEFAULT 0,
    
    -- Transmissão
    transmission_date TIMESTAMP WITH TIME ZONE,
    transmitted_by INTEGER,
    
    -- Auditoria
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_payroll_transmitted_by FOREIGN KEY (transmitted_by) 
        REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_payroll_created_by FOREIGN KEY (created_by) 
        REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT check_status_valid CHECK (status IN ('draft', 'processed', 'transmitted', 'paid', 'cancelled'))
);

-- Índices
CREATE INDEX idx_payroll_period ON payrolls(payroll_period);
CREATE INDEX idx_payroll_company ON payrolls(company_code);
CREATE INDEX idx_payroll_status ON payrolls(status);
CREATE INDEX idx_payroll_created ON payrolls(created_at);
CREATE UNIQUE INDEX idx_payroll_period_company ON payrolls(payroll_period, company_code);


-- ============================================================================
-- Tabela: payslips (Contracheques Individuais)
-- ============================================================================

CREATE TABLE IF NOT EXISTS payslips (
    id SERIAL PRIMARY KEY,
    payroll_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    
    -- Dados do funcionário
    employee_name VARCHAR(180) NOT NULL,
    employee_document VARCHAR(20) NOT NULL,  -- CPF
    position VARCHAR(120) NOT NULL,
    department VARCHAR(120) NOT NULL,
    
    -- Valores
    gross_salary NUMERIC(14, 2) NOT NULL,
    total_earnings NUMERIC(14, 2) NOT NULL,
    total_discounts NUMERIC(14, 2) NOT NULL,
    net_salary NUMERIC(14, 2) NOT NULL,
    
    -- Auditoria de acesso
    accessed_at TIMESTAMP WITH TIME ZONE,
    downloaded_at TIMESTAMP WITH TIME ZONE,
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_payslip_payroll FOREIGN KEY (payroll_id) 
        REFERENCES payrolls(id) ON DELETE CASCADE,
    CONSTRAINT fk_payslip_employee FOREIGN KEY (employee_id) 
        REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT uq_payslip_unique UNIQUE (payroll_id, employee_id)
);

-- Índices
CREATE INDEX idx_payslip_payroll ON payslips(payroll_id);
CREATE INDEX idx_payslip_employee ON payslips(employee_id);
CREATE INDEX idx_payslip_employee_name ON payslips(employee_name);
CREATE INDEX idx_payslip_accessed ON payslips(accessed_at);
CREATE INDEX idx_payslip_downloaded ON payslips(downloaded_at);


-- ============================================================================
-- Tabela: payslip_details (Linhas do Contracheque)
-- ============================================================================

CREATE TABLE IF NOT EXISTS payslip_details (
    id SERIAL PRIMARY KEY,
    payslip_id INTEGER NOT NULL,
    
    -- Tipo de linha
    line_type VARCHAR(20) NOT NULL,  -- "earning" ou "discount"
    description VARCHAR(180) NOT NULL,
    value NUMERIC(14, 2) NOT NULL,
    
    -- Referência externa (ESOCIAL, etc)
    reference_id VARCHAR(100),
    
    -- Auditoria
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_payslip_detail FOREIGN KEY (payslip_id) 
        REFERENCES payslips(id) ON DELETE CASCADE,
    CONSTRAINT check_line_type_valid CHECK (line_type IN ('earning', 'discount'))
);

-- Índices
CREATE INDEX idx_payslip_detail_payslip ON payslip_details(payslip_id);
CREATE INDEX idx_payslip_detail_type ON payslip_details(line_type);
CREATE INDEX idx_payslip_detail_reference ON payslip_details(reference_id);


-- ============================================================================
-- Tabela: payroll_audit_events (Auditoria de Folha de Pagamento)
-- ============================================================================

CREATE TABLE IF NOT EXISTS payroll_audit_events (
    id SERIAL PRIMARY KEY,
    
    -- Entidades relacionadas
    payroll_id INTEGER,
    payslip_id INTEGER,
    
    -- Evento
    action VARCHAR(50) NOT NULL,
    -- Valores típicos:
    -- - payroll_created
    -- - payroll_status_changed
    -- - payslip_accessed
    -- - payslip_downloaded
    -- - payroll_transmitted
    
    description VARCHAR(500) NOT NULL,
    
    -- Auditoria
    user_id INTEGER NOT NULL,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_audit_payroll FOREIGN KEY (payroll_id) 
        REFERENCES payrolls(id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_payslip FOREIGN KEY (payslip_id) 
        REFERENCES payslips(id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE RESTRICT
);

-- Índices
CREATE INDEX idx_audit_payroll ON payroll_audit_events(payroll_id);
CREATE INDEX idx_audit_payslip ON payroll_audit_events(payslip_id);
CREATE INDEX idx_audit_action ON payroll_audit_events(action);
CREATE INDEX idx_audit_user ON payroll_audit_events(user_id);
CREATE INDEX idx_audit_created ON payroll_audit_events(created_at);


-- ============================================================================
-- Dados Iniciais de Teste (SEED DATA)
-- ============================================================================

-- Inserir usuário RH (se não existir)
INSERT INTO users (username, email, full_name, password_hash, is_active, created_at)
VALUES (
    'rh_user',
    'rh@universo-eletronica.com',
    'Gerente RH',
    'hash_aqui',  -- Use bcrypt em produção
    true,
    CURRENT_TIMESTAMP
)
ON CONFLICT (username) DO NOTHING;

-- Inserir folha de teste agosto/2026
INSERT INTO payrolls (payroll_period, company_code, status, total_gross, total_discounts, total_net, created_by)
VALUES (
    '2026-08',
    'universo_eletronica',
    'draft',
    15000.00,
    3000.00,
    12000.00,
    (SELECT id FROM users WHERE username = 'rh_user' LIMIT 1)
)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Permissões e Roles (Recomendado)
-- ============================================================================

-- Permissões específicas de contracheques
-- INSERT INTO permissions (name, description) VALUES
-- ('payroll.view_all', 'Visualizar todas as folhas de pagamento'),
-- ('payroll.view_own', 'Visualizar seu próprio contracheque'),
-- ('payroll.create', 'Criar folhas de pagamento'),
-- ('payroll.transmit', 'Transmitir folhas de pagamento'),
-- ('payroll_audit.view', 'Visualizar auditoria de folha de pagamento');

-- ============================================================================
-- VIEWS ÚTEIS
-- ============================================================================

-- View: Resumo de folhas por período
CREATE OR REPLACE VIEW payroll_summary AS
SELECT 
    payroll_period,
    company_code,
    status,
    COUNT(*) as payslip_count,
    SUM(total_gross) as period_total_gross,
    SUM(total_discounts) as period_total_discounts,
    SUM(total_net) as period_total_net,
    MAX(created_at) as created_at
FROM payslips
WHERE payroll_id IN (SELECT id FROM payrolls)
GROUP BY payroll_period, company_code, status;

-- View: Contracheques não visualizados
CREATE OR REPLACE VIEW payslips_unread AS
SELECT 
    p.id,
    p.payroll_id,
    p.employee_name,
    p.employee_document,
    p.net_salary,
    pr.payroll_period,
    pr.created_at
FROM payslips p
JOIN payrolls pr ON p.payroll_id = pr.id
WHERE p.accessed_at IS NULL
ORDER BY pr.payroll_period DESC, p.employee_name;

-- View: Auditoria de contracheques por funcionário
CREATE OR REPLACE VIEW payslip_access_log AS
SELECT 
    p.employee_name,
    p.employee_document,
    pr.payroll_period,
    pr.status,
    p.accessed_at,
    p.downloaded_at,
    pae.created_at as audit_created_at,
    pae.action,
    u.full_name as actor_name
FROM payslips p
JOIN payrolls pr ON p.payroll_id = pr.id
LEFT JOIN payroll_audit_events pae ON pae.payslip_id = p.id
LEFT JOIN users u ON pae.user_id = u.id
ORDER BY pr.payroll_period DESC, p.employee_name;

-- ============================================================================
-- Testes de Integridade (QUERIES DE VALIDAÇÃO)
-- ============================================================================

-- Verificar se tabelas foram criadas
/*
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name LIKE 'payroll%';

-- Verificar índices
SELECT indexname FROM pg_indexes 
WHERE tablename LIKE 'payroll%' OR tablename LIKE 'payslip%';

-- Verificar constraints
SELECT constraint_name, table_name FROM information_schema.table_constraints 
WHERE table_name LIKE 'payroll%' OR table_name LIKE 'payslip%';
*/
