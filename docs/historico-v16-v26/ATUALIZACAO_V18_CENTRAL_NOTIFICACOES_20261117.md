# SÊNTICO V18 — Central interna de notificações / histórico de atividades

Data: 17/11/2026. Base: pacote V17 com correções de orçamentos com 10 fotografias.

## Mudança solicitada

A V18 **não usa pop-up do navegador ou push para comunicar novas atividades**. O painel apresenta as movimentações no sino e em **Atividades recentes**, com o botão **Ampliar / Ver tudo**. O menu lateral passa a ter **Notificações**, com página própria no endereço `/notificacoes`.

A central interna oferece pesquisa por texto, equipamento ou nome, filtros por módulo, tipo de ação, colaborador, número da OS, datas e somente não lidas. Os resultados apresentam data, quem fez, o que fez, número da OS quando aplicável, equipamento, descrição e observações; há navegação para o registro e ações de marcar como lida. A lista é paginada. O período usa o calendário de Pernambuco (America/Recife).

## Eventos operacionais implementados

- **Laboratório:** criação/atualização/inativação da OS; alterações de status; análise concluída; mudança de etapas; elaboração de solicitações de material; saída e retorno de pintura externa.
- **Orçamentos:** criação, revisão, edição, exclusão e emissão, além do encaminhamento para orçamento depois da análise e movimentações comerciais relacionadas.
- **Compras/materiais:** solicitações, aprovação, compra, recebimento, entrega ao laboratório; criação, atualização, recebimento e exclusão de pedidos.
- **Estoque:** cadastro e alteração de itens; entradas e saídas de material; retorno de itens e movimentações ligadas à OS quando os dados estão presentes.
- **Financeiro:** criação/edição/exclusão de lançamentos, baixa e estorno.
- **Cadastros:** criação e atualização de clientes; criação, edição e desativação de usuários (visíveis somente à Gestão).

Ações de consulta/leitura não geram notificações. Os eventos passam a ser gravados **a partir da instalação da V18**; as notificações antigas reconhecidas permanecem acessíveis, mas não têm retroativamente todos os novos metadados (autor/equipamento). Este histórico operacional é uma camada de acompanhamento e **não substitui o log/auditoria de todos os campos do banco**; fluxos menos comuns que não são listados acima não estão incluídos nesta versão.

## Perfis e confidencialidade

- **Gestão e super_admin:** todos os módulos, inclusive financeiro e gestão de usuários.
- **ADM:** somente atividades de orçamento; não recebe dados financeiros, do estoque ou laboratório que não sejam de orçamento.
- **Técnico / laboratório:** somente módulos operacionais autorizados. Não recebe lançamentos financeiros ou preços sensíveis; as mensagens compartilhadas não exibem montantes.
- **Compras, estoque e demais funções:** somente os módulos efetivamente autorizados. As regras são executadas no backend, inclusive em filtros, leitura e marcação de mensagens.

O autor vê sua própria movimentação se seu perfil permitir. Quando uma OS passa para "Aguardando orçamento", o evento é destinado ao perfil de orçamentos, e a equipe de laboratório recebe um registro técnico do mesmo encaminhamento, sem duplicar aviso para a Gestão.

## Instalação local e proteção dos dados

1. Faça backup do **PostgreSQL e dos uploads** antes de substituir os arquivos. A atualização não apaga dados nem troca volumes.
2. Extraia o ZIP completo em uma pasta local e mantenha o **Docker Desktop aberto**.
3. Inicie apenas **`INICIAR_SENTICO.cmd`**. O instalador migra o banco existente da revisão `20261116_01` para `20261117_01` e reconhece os estados intermediários suportados.
4. Abra `http://127.0.0.1:5184/`, entre com diferentes perfis e acesse **Painel → Sino → Ampliar**, ou **Menu → Notificações**.
5. Não execute `docker compose down -v`, `docker volume rm` ou `docker volume prune`. Não atualize a VPS antes da homologação local.

### Cenário rápido de teste (com dados fictícios)

- Entre com usuário de laboratório e mova a **OS 39405** (cliente CAPRICHE, inversor WEG CFW11) para **Aguardando orçamento**.
- Na central da Gestão, pesquise por `39405`: deve aparecer o responsável, a etapa e o equipamento. Na sessão ADM, deve aparecer o encaminhamento para orçamento. Na sessão de laboratório, o registro técnico de análise concluída.
- Em Compras, registre solicitação, compra, chegada e entrega. Filtre **Compras e materiais** para conferir autor/status/data.
- Lance/baixe um título financeiro na Gestão. Verifique que ADM e técnico não conseguem ler o evento nem filtrar o módulo financeiro via API.
- Com o próprio usuário que fez uma ação, confira que ela aparece na central, desde que o perfil autorize o módulo.
- Teste em 360 px / 390 px / 430 px: filtros empilham, tamanho das fontes se ajusta e a página não exige zoom. O layout desktop permanece com os estilos anteriores.

## Validação executada neste pacote

- Compilação sintática de Python (`compileall`) e dos componentes TSX alterados (`transpileModule`) concluídas.
- **54 testes Python direcionados passaram**, incluindo permissões, orçamento/fotos e fluxos de estoque/compras.
- **28 testes do instalador passaram**; validação sintática dos scripts de catálogo executada.
- Ensaio de integração da API com SQLite validou filtros, pesquisa, Gestão/ADM/técnico e bloqueio de filtro não autorizado.

**Ainda pendente:** o build integral do frontend e a homologação integrada Docker/PostgreSQL/Windows não foram executados porque as dependências NPM/psycopg não estavam disponíveis neste ambiente. Valide em cópia local antes de produção. Nenhuma mudança foi implantada automaticamente na VPS.

## Sobre Web Push da V16

A execução do entregador de notificações push foi **desativada** no backend da V18; não há botão de ativação de push no painel novo. Os arquivos de infraestrutura anteriores permanecem no código por compatibilidade, mas não são usados para entregar as novas atividades. A V18 prioriza exclusivamente o histórico dentro do SÊNTICO.
