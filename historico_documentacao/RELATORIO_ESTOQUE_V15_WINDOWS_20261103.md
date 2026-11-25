# SÊNTICO V15 — Controle de alterações e instalação Windows

Versão de origem: SÊNTICO V14 com interface de Estoque refinada (03/11/2026).

**Escopo:** interface de Estoque, criação de endereços, etiquetas PDF; sem modificação de regras de negócio do Laboratório, Compras ou Financeiro.

**Instalador:** `INSTALAR_SENTICO_V14.ps1` e scripts `scripts_recuperacao/` foram mantidos byte a byte. `INICIAR_SENTICO_V15.cmd` é apenas um atalho adicional.

**Banco:** sem migrations novas, sem limpeza de volumes. A estrutura de dados existente é reutilizada; mudanças de dados decorrentes de criação de endereços pelo usuário ocorrem via API existente.

**Verificações:** frontend TypeScript + Vite compilado com sucesso; Python sem erro de sintaxe; SHA256 verificado. Não houve execução end-to-end no Docker Desktop Windows.

**Observação de lote:** a criação em lote na interface usa chamadas sequenciais ao endpoint de criação de local. Se uma operação intermediária falhar (por exemplo, código já cadastrado), anteriores podem ter sido criadas. Confira o resultado e evite repetir o lote sem revisar os locais.
