# SÊNTICO V31 — Filtro de datas no painel inicial

**Data:** 23/11/2026
**Base:** V30 completa, incluindo correção de rascunhos de orçamentos e temas comemorativos.

## Por que a alteração foi realizada

O painel da V30 contabilizava OS, solicitações e outras pendências antigas que foram importadas de um sistema anterior. Por exemplo, uma OS de 2022 ainda marcada como **Aprovado** podia aparecer entre os serviços a realizar em 2026, prejudicando a leitura das pendências atuais. A V31 oferece uma escolha de intervalo de datas no mesmo local de **Personalizar painel**.

## Como usar

1. Abra **Painel inicial → Personalizar painel**.
2. Em **Período dos indicadores**, escolha: **Todo o histórico**, **Este mês**, **Últimos 30 dias**, **Últimos 90 dias**, **Este ano** ou **Escolher datas**.
3. Para ocultar tudo o que é anterior a uma data específica, escolha **Escolher datas**, informe **somente a data inicial** (por exemplo, **01/11/2026**) e deixe a data final em branco.
4. Clique em **Aplicar período**. Os totais, as filas e os pedidos exibidos no painel serão consultados novamente no banco usando esse intervalo.
5. A seleção fica salva por usuário **neste navegador/dispositivo** e permanece após recarregar a página. A escolha do período não modifica quais áreas estão visíveis.
6. Clique em **Todo o histórico** para voltar a considerar todos os registros. O botão **Mostrar tudo** na barra superior restaura apenas áreas ocultas.

**Padrão inicial:** Todo o histórico. Essa escolha é intencional para não esconder pendências atuais sem a autorização do usuário; quem deseja excluir registros antigos do painel define o início uma vez.

## Qual data entra em cada cartão

- **Laboratório e Orçamentos:** data de entrada/abertura da OS (`laboratory_work_orders.opened_at`). Os status atuais são mantidos, mas as OS com entrada fora do período selecionado não entram nas filas nem nos totais.
- **Compras — solicitações:** data de criação da solicitação de material (`material_requests.created_at`).
- **Compras — pedidos urgentes:** data da compra (`purchase_orders.purchase_date`). O prazo de entrega continua sendo utilizado para classificar pedidos atrasados e próximos.
- **Estoque — materiais ligados a solicitações:** data de criação da solicitação de material.
- **Financeiro — pendências e atrasos:** data de vencimento do lançamento (`financial_entries.due_date`).
- **Financeiro — últimos faturados:** data do faturamento da OS (`laboratory_work_orders.invoiced_at`). Quando um intervalo é aplicado, a contagem e os cinco itens mostrados consideram a **mesma faixa de datas**; sem filtro, mantém o horizonte recente de 30 dias.
- **Equipamentos com entrada:** sem intervalo, conta o mês atual. Com intervalo, conta as entradas de OS dentro das datas selecionadas e exibe no cartão a identificação do período.
- **Notificações e ações rápidas:** não sofrem recorte de datas, porque mostram avisos atuais e comandos de navegação. O acesso aos módulos permanece de acordo com o perfil.

## Escopo e limitações

Este filtro altera **somente o painel inicial**: ele não apaga dados importados, não muda status e não restringe resultados das telas completas de Laboratório, Compras ou Financeiro. Uma OS antiga continua disponível normalmente quando acessada pelo módulo ou pelo seu link direto. Se a migração anterior tiver substituído a data original de entrada/criação pela data atual, o filtro temporal não consegue identificar esse registro como antigo; seria necessário identificar a origem dos registros em separado.

O servidor valida as datas e aplica os mesmos critérios às contagens e às amostras de cada fila. A autorização de acesso continua na API: apenas Gestão consulta Financeiro, mesmo quando alguém altera manualmente os parâmetros da URL. Não houve mudança de banco, migração Alembic, volumes Docker, nome do Compose ou instalador.

## Arquivos principais

- `codigo-fonte/apps/api/app/dashboard/service.py` — filtro aplicado às consultas SQL.
- `codigo-fonte/apps/api/app/dashboard/router.py` — parâmetros `periodo`, `inicio` e `fim`.
- `codigo-fonte/apps/api/app/dashboard/schemas.py` — indicador de período aplicado.
- `codigo-fonte/apps/web/src/features/dashboard/dashboardPeriod.ts` — opções, armazenamento e validação.
- `codigo-fonte/apps/web/src/features/dashboard/Dashboard.tsx` — controles e atualização do painel.
- `codigo-fonte/apps/web/src/features/dashboard/types.ts` — tipagem.
- `codigo-fonte/apps/web/src/features/dashboard/dashboard.css` — estilos claro/escuro e celular.
- `codigo-fonte/apps/api/tests/test_dashboard_v31_period.py` — cobertura de SQL, intervalos e permissões.

## Validação e homologação

- **Backend:** 20 testes de painel/perfis/período aprovados.
- **Regressão V30:** testes dirigidos de revisão de orçamento aprovados, com um teste dependente de banco externo não executado.
- **Instalador:** 45 testes aprovados.
- **Frontend:** arquivo auxiliar `dashboardPeriod.ts` compilado isoladamente e testado; arquivos TypeScript/TSX verificados quanto à sintaxe.
- **CSS:** análise de parsing sem erros.
- **Pendente:** build completo React/Vite e homologação real com PostgreSQL/Docker/Windows (dependências JavaScript ausentes neste ambiente).

**Para homologar:** faça backup do banco e dos uploads, extraia o ZIP completo, abra Docker Desktop, execute `INICIAR_SENTICO.cmd` e teste com OS antigas reais e OS recentes. Use um usuário Gestão e outro LAB para validar os filtros, os totais, a separação de perfis e a persistência da preferência. **Não atualize a VPS antes dessa verificação.**
