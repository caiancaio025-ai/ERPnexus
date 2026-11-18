# SÊNTICO V24 — Correção da área interna da O.S. no celular

## Diagnóstico
Na V23, o cabeçalho com muitas ações, nove abas dispostas em diversas linhas e o rodapé com botões grandes consumiam quase toda a altura do detalhe da O.S. em celulares. O resultado era uma área estreita para consultar e editar dados, principalmente na aba Orçamento.

## Alterações

- **Detalhe da O.S. em tela cheia** com altura adaptada à viewport (`100dvh`), cabeçalho compacto, abas em uma faixa e rodapé com dois botões lado a lado.
- **Área de conteúdo independente**, com rolagem vertical e largura total: o usuário consegue consultar laudo, valores, dados técnicos, status, documentos, materiais e histórico.
- **Abas horizontais** com toque e arraste: a aba selecionada é deslocada automaticamente para dentro da área visível no celular.
- **Ações extras recolhidas** atrás do botão Ações no cabeçalho; nenhuma ação foi removida. O botão X permanece no cabeçalho.
- **Aba Orçamento**: campos de componentes passam a ocupar o espaço disponível, evitando uma tabela que exige rolagem horizontal; dados completos do cliente e equipamento permanecem acessíveis no controle expansível.
- **Temas claro e escuro** tratados com contraste independente; o desktop não recebe os ajustes de viewport.

## Escopo

Arquivos de aplicação alterados:

- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/components/QuoteEditor.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `codigo-fonte/apps/web/src/shared/theme/light-theme.css`

## Proteção dos dados

Nenhuma migração de banco, regra financeira, fluxo de aprovação, permissão ou volume foi alterado. O projeto do Docker e os scripts do instalador único continuam os da V23. Antes de atualizar, faça backup do PostgreSQL e dos uploads. Não use `docker compose down -v`.

## Verificações realizadas nesta entrega

- 45 testes do instalador e compatibilidade existentes aprovados.
- 55 arquivos TS/TSX não declarativos passaram na análise sintática de transpilação; CSS dos dois arquivos alterados sem erros de parsing.
- Prévia de layout estático no Chromium: larguras 320, 360, 390 e 430 px, nos dois temas, sem rolagem horizontal da página e com área vertical para o conteúdo; teste também em 1280 px para conferir estilos não mobile.
- Verificado deslocamento horizontal para revelar a aba ativa e expansão do menu de ações em prévia estática.

**Limites:** as prévias são um ensaio de CSS/estrutura com dados fictícios, não são a aplicação React conectada ao PostgreSQL. A compilação integral NPM e a homologação no Docker/Windows ainda precisam ocorrer no seu ambiente antes da VPS.

## Como homologar em Docker

1. Extraia o ZIP em uma nova pasta no Windows e mantenha um backup dos dados.
2. Abra o Docker Desktop e execute `INICIAR_SENTICO.cmd` na raiz da pasta extraída.
3. Em um celular, abra Laboratório e selecione uma O.S. real de testes.
4. Confira as nove abas, arrastando horizontalmente. Abra **Ações** para ver Etiqueta, Receitas/parcelas (quando autorizado) e demais operações.
5. Teste o formulário de Orçamento, inclusão de itens, edição de valores, fotos, salvar rascunho e consulta PDF.
6. Confira o mesmo registro no desktop e os temas claro/escuro.

Não atualizei a VPS.
