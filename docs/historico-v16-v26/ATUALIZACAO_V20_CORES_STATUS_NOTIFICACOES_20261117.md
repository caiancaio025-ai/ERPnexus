# SÊNTICO V20 — Cores dos status, notificações e nome “Analisado”

**Base:** pacote completo V19 de 17/11/2026, preservado integralmente com alterações pontuais na aparência clara e na apresentação dos status. Esta atualização não é um patch solto: o ZIP contém o instalador único, o código-fonte e o histórico de documentação.

## O que mudou

### 1. Cores semânticas recuperadas no tema claro

O CSS global V19 substituía fundos de etiquetas por um único tom azulado, removendo a diferenciação dos status. A V20 inclui uma folha específica importada depois da V19 (`apps/web/src/shared/theme/light-semantic-colors.css`), **somente para o modo claro**.

- **Vermelho:** Sem conserto (`no_repair`), Reprovado, Cancelado e títulos financeiros atrasados.
- **Verde:** Aprovado, Concluído, Entregue/Recebido, situações de pagamento concluído.
- **Amarelo/âmbar:** Aguardando análise, Aguardando aprovação, Aguardando peças, Reparando e pendências.
- **Azul:** Entrada/Recebido (status de OS), Orçamento emitido, movimentações informativas.
- **Turquesa:** Analisado e Em testes.
- **Roxo:** Garantia, Faturado e informações do estoque na Central de Notificações.

A associação entre cor e situação segue **o código real do registro**, não depende apenas de texto livre. Painel, Laboratório, Clientes, Compras, Comercial e Financeiro receberam tratamentos específicos de etiquetas e destaques suaves. Não foi aplicada troca de cores ao tema escuro.

### 2. “Em análise” agora aparece como “Analisado”

- A apresentação de `in_analysis` foi ajustada em Laboratório, Clientes, notificações e relatórios técnicos.
- Itens antigos com texto “Em análise” são convertidos **na exibição**, inclusive mensagens de notificações e notas do histórico.
- Configurações antigas que retornam do banco a legenda “Em análise” são apresentadas como “Analisado” na tela, com o mesmo código `in_analysis`.
- O histórico de migrações do banco **não foi reescrito**. Não há alteração de status armazenado nem exigência de migração.

**Importante:** o fluxo técnico e as regras existentes para `in_analysis` continuam os mesmos. Esta é uma mudança de legenda, não a introdução de uma etapa nova de conclusão de diagnóstico.

### 3. Central de Notificações mais agradável

- Etiquetas e ícones recebem cor moderada por **setor**: Laboratório (turquesa), Orçamentos (azul), Compras (âmbar), Estoque (roxo), Financeiro (verde), Comercial (rosa), Colaboradores (índigo) e Configurações (azul acinzentado).
- Notificações não lidas recebem destaque sutil da própria cor do módulo, sem eliminar o contraste do texto.
- A lista compacta do sino e o resumo do painel também recebem a indicação colorida por setor.
- Resumo de avisos, filtros e cartões principais do painel recebem bordas coloridas leves; o visual continua branco, limpo e profissional.
- As regras de acesso **não mudaram**: Gestão acompanha todos os setores; ADM vê somente os eventos de orçamento; técnicos não recebem dados financeiros.

## Arquivos principais alterados

- `codigo-fonte/apps/web/src/shared/theme/light-semantic-colors.css` (novo)
- `codigo-fonte/apps/web/src/main.tsx`
- `codigo-fonte/apps/web/src/shared/i18n/portugues.ts`
- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/customers/CustomerMaster.tsx`
- `codigo-fonte/apps/web/src/features/notifications/NotificationCenter.tsx`
- `codigo-fonte/apps/web/src/features/dashboard/Dashboard.tsx`
- `codigo-fonte/apps/api/app/laboratory/router.py`
- `codigo-fonte/apps/api/app/laboratory/quote_pdf.py`
- `codigo-fonte/apps/api/app/tracking/router.py`
- `testes_instalador/test_v20_cores_e_status.py` (novo)

## Validações executadas

- 40 testes de contrato/instalador passaram.
- 22 testes da configuração e dos estados do laboratório passaram.
- Verificação sintática dos **55 arquivos TS/TSX** do frontend via compilador TypeScript sem resolução de bibliotecas: aprovada.
- CSS lido pelo parser `tinycss2` sem erros de parsing.
- Testes funcionais isolados de tradução, incluindo `OS OS-30740 · Warranty` e `OS OS-30740 · Em análise`: aprovados.
- Arquivos Python alterados passaram na compilação sintática.

**Ainda pendente:** o `npm run build` foi tentado, mas não concluiu porque as dependências React não estão instaladas neste ambiente. Faltam também execução em Docker/PostgreSQL e conferência visual em navegadores/celulares reais. Essas verificações são necessárias antes da implantação de produção. Nenhum banco ou VPS foi atualizado aqui.

## Homologação local recomendada

1. Faça backup dos volumes PostgreSQL e de uploads, especialmente se já houver dados reais.
2. Extraia o **ZIP V20 completo** em pasta nova no Windows e abra o Docker Desktop.
3. Execute somente `INICIAR_SENTICO.cmd` e entre em `http://127.0.0.1:5184/`.
4. Escolha **Tema claro**, e abra uma OS com status **Sem conserto**: a etiqueta deverá estar vermelha. Compare com uma **Aprovada** (verde), **Aguardando aprovação** (âmbar) e **Analisado** (turquesa).
5. Acesse a Central de Notificações e o sino do Painel; valide cores por módulo e legibilidade de cartões lidos/não lidos.
6. Confira o tema escuro, a versão mobile e o PDF da OS; nada deve ter mudado em comportamento, permissões ou valores.
7. Se o navegador mantiver CSS anterior em cache, pressione `Ctrl+F5` e reabra a página. Em PWA instalada, encerre e reabra o aplicativo.

**Não execute** `docker compose down -v`, `docker volume prune` ou comandos que apaguem volumes. O projeto Compose e a revisão Alembic `20261117_01` são os mesmos da V19; não há nova migração.
