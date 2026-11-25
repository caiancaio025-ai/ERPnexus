# SÊNTICO V26 — Painel inicial personalizável

## Objetivo
Permitir que cada usuário organize os quadros do painel sem precisar navegar por muitas informações ao mesmo tempo.

## Funcionamento

1. Entre no **Painel**.
2. Clique em **Personalizar painel**.
3. Escolha as áreas em **Visível / Oculta** para combinar vários setores ou clique em **Somente esta** para focar em uma área.
4. Para reativar tudo, clique em **Mostrar tudo** ou **Mostrar todas as áreas disponíveis**.

O painel padrão permanece completo. As preferências são lembradas individualmente pelo navegador para o ID do usuário autenticado. Um segundo celular/computador terá sua própria configuração; as escolhas não são gravadas no servidor.

## O que é controlado

- **Laboratório** — indicadores e filas de OS, além de entradas mensais.
- **Orçamentos** — indicadores e filas de orçamento por concluir.
- **Compras** — solicitações, pedidos, atrasos e entregas previstas.
- **Financeiro** — vencimentos, pendências e faturamentos, somente quando autorizados na API.
- **Estoque** — filas autorizadas de recebimento e separação.
- **Notificações** — cartões de atividades recentes e indicador de notificações do painel; o sino de acesso à central continua acessível.
- **Ações rápidas** — atalhos do painel para operações frequentes.

A lista de opções deriva das informações que a API já disponibiliza ao perfil conectado. O mecanismo **não concede acesso** a módulos nem expõe dados financeiros de perfis que não recebem esses dados do servidor.

## Arquivos alterados

- `codigo-fonte/apps/web/src/features/dashboard/Dashboard.tsx`
- `codigo-fonte/apps/web/src/features/dashboard/dashboardPreferences.ts` (novo)
- `codigo-fonte/apps/web/src/features/dashboard/dashboard.css`
- `codigo-fonte/apps/web/src/shared/theme/light-theme.css`
- `testes_instalador/test_v26_painel_preferencias.cjs` (novo)

## Banco e implantação

- Sem migração Alembic.
- Sem alteração de endpoints, banco, permissões ou volumes Docker.
- Instalador único mantido: `INICIAR_SENTICO.cmd`.
- Faça backup do banco e uploads antes de qualquer atualização em ambiente com dados reais.

## Testes já executados

- 11 verificações de seleção e persistência por usuário (Node.js).
- 45 testes automatizados do instalador (pytest).
- 56 arquivos TS/TSX analisados sem erro sintático.
- Regras CSS analisadas sem erro sintático.

**Pendente:** compilação integral com dependências NPM, renderização e homologação em Docker/Windows. Teste os dois temas em larguras desktop e mobile, alternando entre Gestão, ADM, LAB e Compras, antes de atualizar a VPS.
