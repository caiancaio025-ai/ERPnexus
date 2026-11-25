# SÊNTICO ERP — Atualização V5 (26/10/2026)

**Base de comparação:** SÊNTICO Green Estoque V4 — Todas as Solicitações (26/10/2026).
**Escopo:** nomes independentes Compras/Estoque, identidade canônica de item existente, tema azul-marinho e pesquisa combinada do Laboratório. **Sem nova migration.** O último head Alembic continua `20261026_02`.

## Mudanças

1. **Compras:** campo "Título / descrição da compra" identificado como comercial; área de Estoque mostra em duas colunas o título da compra e o nome técnico efetivo. Ao optar por cadastrar um item novo, o campo "Nome técnico do novo item" é independente e obrigatório no recebimento. Não faz mais cópia silenciosa do título comercial. Antes do recebimento, pode ficar vazio, conforme o fluxo original.
2. **Estoque existente:** ao selecionar um cadastro por código ou nome, a tela apresenta o nome canônico do item já registrado. A API valida empresa, situação ativa e modo de controle por quantidade e grava o nome canônico. Uma compra com destino existente fora do filtro continua aparecendo no seletor (`selected_id`), limitado à mesma empresa. Pedidos já recebidos permanecem protegidos contra edição física sem estorno.
3. **Solicitações de Compras avulsas e OS:** o componente compartilhado também passa a exibir o nome do item já cadastrado ao vinculá-lo; o recebimento existente continua associado pelo ID, sem alterar a etiqueta.
4. **Estoque UX:** corrigido branco persistente do mapa (seletor CSS específico); cartões, diálogos e campos de seleção ficam no azul-marinho. Adicionados filtros rápidos Todos / Disponíveis / Sem local / Sem saldo, contador, foco visível e melhor contraste. Nenhuma alteração no modelo de localização, fotos, custos, etiquetas ou movimentações.
5. **Laboratório:** a pesquisa textual agora se combina com mês, ano, empresa e status. A própria API já aplicava os critérios em conjunção (AND); o erro estava na montagem da URL no frontend, que omitia filtros sempre que havia texto. Paginação continua reiniciando na página 1 ao alterar filtros.

## Arquivos

Foram alterados 13 arquivos de código/testes, incluindo um arquivo Python novo (`stock_names.py`) e o novo teste (`test_purchase_stock_names_v5.py`). Nenhuma migration nova, nem arquivos de configuração de produção.

## Validação

- **323 testes aprovados** em regressão selecionada (ambiente Python, sem banco real).
- Testes específicos de nome técnico, vínculo com item existente, pesquisa combinada e layout: aprovados.
- Quatro arquivos TSX passaram na análise sintática do TypeScript (`transpileModule`), sem type-check completo.
- CSS analisado com `tinycss2`: zero erros estruturais nos três CSS alterados.
- Suíte completa: **não executada integralmente**; nove módulos de teste exigem `psycopg` ausente no ambiente desta análise. O teste do manifesto financeiro histórico também foi excluído porque os arquivos CSV sensíveis não fazem parte da cópia de desenvolvimento sanitizada.
- **Não foram executados** build completo da Web, migrations PostgreSQL reais e homologação funcional em navegador.
- ZIP integral e ZIP de patch testados por CRC e SHA256.

## Instalar / atualizar em Windows (somente local)

**Opção A — ZIP completo:** extraia em uma pasta nova. Abra o Docker Desktop Linux. Execute `INICIAR_SENTICO_GREEN.cmd` na raiz. Atenção: o projeto Compose da distribuição utiliza o nome fixo `sentico-dev-entrega`; apenas mudar de pasta NÃO isola volumes/containers. Para testar versões simultâneas, use projeto/volumes/portas distintos.

**Opção B — Patch V4 → V5:** faça backup da pasta e do banco PostgreSQL do teste atual. Extraia o ZIP "SOMENTE_ALTERACOES" na raiz onde se encontram `codigo-fonte` e `INICIAR_SENTICO_GREEN.cmd`, substituindo somente os arquivos indicados. Preserve `.env.dev`, Compose e volumes. Depois, dentro de `codigo-fonte`, execute:

```powershell
docker compose --env-file .env.dev -f compose.dev.yml config --quiet
docker compose --env-file .env.dev -f compose.dev.yml up -d --build
docker compose --env-file .env.dev -f compose.dev.yml ps
```

O código atualizado mantém o mesmo head de migrations da V4; não invente novas migrations ou execute `stamp`.

**Homologação prioritária:** (a) compra com título diferente do nome técnico; (b) seleção de item existente, nome assumido e saldo somado; (c) seleção de item de outra empresa rejeitada; (d) área do mapa em azul; (e) filtro Laboratório mês+ano+status+empresa e pesquisa simultânea; (f) troca de páginas e limpeza da pesquisa. Confirme login, criação/edição de OS, Compras e Estoque.

**Segurança:** uso exclusivo local, sem dados de produção nem acesso à VPS. Não executar `docker compose down -v`, apagar volumes ou substituir `.env` real. A versão contém um usuário fictício de teste previsto no pacote anterior; não publicar esse login em servidores acessíveis externamente.
