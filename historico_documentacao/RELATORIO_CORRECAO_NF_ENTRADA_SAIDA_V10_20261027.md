# SÊNTICO ERP V10 — Três NFs de entrada e três de saída por OS

## Correção de escopo
A V9 havia interpretado incorretamente o pedido como três NFs de garantia.
A V10 apresenta três pares de NF de entrada/saída na abertura e edição da OS:
- **1ª passagem:** `entry_invoice` e `exit_invoice` (campos existentes, preservados).
- **2ª passagem:** `entry_invoice_2` e `exit_invoice_2`.
- **3ª passagem:** `entry_invoice_3` e `exit_invoice_3`.

Os seis números podem ser pesquisados pela pesquisa do Laboratório **combinada** aos filtros de mês, ano, status e empresa. A listagem identifica notas com E1–E3 e S1–S3. Campos de notas 2 e 3 podem ficar em branco até o retorno.

**Atenção aos dados da V9:** `warranty_invoice`, `warranty_invoice_2`, `warranty_invoice_3` são preservados no banco e continuam pesquisáveis; se uma OS os tiver preenchidos, são exibidos na edição em uma seção claramente marcada como **histórico legado**, sem converter automaticamente notas antigas em entradas ou saídas (a natureza da NF precisa ser conferida por uma pessoa).

As chaves de acesso de 44 dígitos existentes continuam ligadas ao **primeiro par**; não foram criadas novas chaves de acesso para os pares 2 e 3.

## Migração
- Nova revisão: `20261027_03` (revisão anterior: `20261027_02`).
- Quatro colunas opcionais VARCHAR(80) e quatro índices na tabela `laboratory_work_orders`.
- Sem apagamento, renomeação, conversão de notas antigas ou reinicialização do banco.
- Downgrade bloqueado por segurança.
- Instalador local mantém configuração da V9 e reconhece a nova revisão Alembic.

## Arquivos de código alterados (V9 → V10)
- `INSTALAR_SENTICO_DEV.ps1`
- `codigo-fonte/apps/api/app/laboratory/models.py`
- `codigo-fonte/apps/api/app/laboratory/schemas.py`
- `codigo-fonte/apps/api/app/laboratory/service.py`
- `codigo-fonte/apps/api/app/laboratory/router.py`
- `codigo-fonte/apps/api/migrations/versions/20261027_03_three_entry_exit_invoices.py` (novo)
- `codigo-fonte/apps/api/tests/test_v10_three_entry_exit_invoices.py` (novo)
- `codigo-fonte/apps/web/src/features/laboratory/types.ts`
- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`

## Verificações executadas
- 61 testes selecionados (Laboratório, NF, contratos e regressões) passaram.
- Sintaxe Python aprovada via `compileall`.
- Sintaxe TSX conferida com transpilation TypeScript; 0 diagnósticos de erro.
- SQL PostgreSQL da migration gerado e verificado (4 ADD COLUMN, 4 CREATE INDEX).
- Integridade CRC e SHA256 dos ZIPs verificada.
- **Não executados neste ambiente:** build completo do frontend, migration em PostgreSQL real, end-to-end no navegador e homologação Docker.

## Atualização local segura
1. Fazer backup testado do PostgreSQL local e dos arquivos atuais antes da atualização.
2. Para ambiente V9, copiar o conteúdo do pacote **somente alterações** mantendo caminhos relativos. **Não** sobrescrever `.env.dev` e **não** remover volumes.
3. Executar o instalador já existente com Docker Desktop iniciado. Ele deve migrar para `20261027_03`.
4. Homologar: abrir OS existente com NF, conferir preservação de Entrada 1 e Saída 1; cadastrar E2/S2 e E3/S3, salvar, recarregar, pesquisar números, conferir filtragem simultânea mês/ano/status/empresa; verificar dados antigos de garantia onde houver.
5. Não implantar em VPS de produção até validar migrations e testes em cópia do banco.

O pacote não contém banco real, anexos privados ou `.env.dev`.
