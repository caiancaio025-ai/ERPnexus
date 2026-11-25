# SÊNTICO V47 — Cabeçalhos fixos nas tabelas

## O que foi implementado

A faixa de títulos das colunas permanece visível no topo **da própria tabela** enquanto o usuário rola os registros, tanto no tema escuro quanto no claro. O conteúdo continua rolando normalmente por baixo da faixa.

A área de tabelas extensas passou a ter uma altura máxima responsiva de até 70% da altura da tela (limite de 760 px). Dessa forma, a tabela é percorrida internamente, inclusive quando possui muitas colunas e exige rolagem horizontal. O restante da página mantém sua rolagem normal.

## Listagens contempladas

- Laboratório: O.S. (OS, Cliente, Equipamento/Série, Localização, NFs, Garantias, Status etc.) e relatório de produção técnica.
- Comercial: tabelas de patrimônio, propostas e itens em edição de orçamento.
- Colaboradores: listagem dos usuários/colaboradores.
- Compras: pedidos e relatório de gastos.
- Financeiro: planejamento/visão mensal em grade.
- Clientes: tabelas de documentos e relacionamentos.

**Importante:** no celular, a lista de O.S. do Laboratório permanece em cartões, sem cabeçalho tabular nem restrição artificial de altura. Na impressão, os elementos retornam ao fluxo normal para não truncar linhas.

## Arquivos

- `codigo-fonte/apps/web/src/shared/ui/sticky-tables.css` (novo)
- `codigo-fonte/apps/web/src/main.tsx` (importação do estilo)
- `testes_instalador/test_v47_cabecalhos_tabelas.py` (novo teste de regressão)

## Compatibilidade e segurança

- Base V46 preservada.
- Sem alterações de banco de dados, APIs, permissões ou cálculo dos módulos.
- Sem migração nova nesta versão. A migração anterior V46 continua necessária se ainda não foi aplicada.
- Instalador único `INICIAR_SENTICO.cmd` mantido.
- Não altera nem instala nada na VPS.

## Testes

- 60 testes do pacote/instalador passaram.
- Verificação visual automatizada no Chromium: cabeçalhos fixos em Laboratório, Comercial e Compras, em tema claro e escuro, com rolagem interna.
- Verificação do comportamento mobile da listagem de O.S. e do modo impressão.
- A compilação integral React/Vite e a homologação com dados reais no Docker/Windows permanecem pendentes.

## Como validar no Docker

1. Faça backup dos volumes PostgreSQL e uploads.
2. Extraia o pacote em uma pasta nova no Windows.
3. Abra o Docker Desktop e execute `INICIAR_SENTICO.cmd`.
4. Entre no **Laboratório**, na listagem de O.S.; posicione o ponteiro dentro da tabela e role para baixo.
5. Confirme que **O.S., Cliente, Equipamento/Série, Localização, NF, Status etc.** permanecem no topo da lista.
6. Teste também Comercial, Compras e Colaboradores; alterne os temas claro/escuro.
7. No celular, confira que a listagem do Laboratório permanece em cartões.
