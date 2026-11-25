# SÊNTICO — Entrega técnica Estoque V6 (26/10/2026)

## Base, escopo e preservação

Base de código: `SENTICO_GREEN_ESTOQUE_V5_NOMES_TEMA_FILTROS_20261026.zip`, sem segredos nem banco de produção.
Aplicação V6: ajustes nos módulos API + Web de Estoque, nova migration Alembic `20261026_03`, testes e instalador local. A integração anterior Compras → Estoque → Laboratório/OS não foi substituída. Nenhuma alteração foi aplicada na VPS.

## Funcionalidades

- Tela principal: fotos ampliadas (152 × 138 px no desktop); nome, descrição, saldo e localização em destaque; pesquisa por texto, etiqueta, localização, tipo, subtipo, encapsulamento.
- Cadastro manual: **sem campo de empresa na interface**; o `company_code` permanece **internamente** para manter integrações e integridade dos registros existentes. Campos: nome, quantidade ou série única, descrição, foto (upload ou câmera), categoria técnica, subtipo, encapsulamento, custo por permissão, fabricante/modelo e endereço.
- Catálogo configurável persistido em banco: `inventory_component_categories`, `inventory_component_subtypes`, `inventory_component_formats` (já existia). API de inclusão/renomeação de tipo e subtipo. Categoria → subtipo → formato/encapsulamento; categoria determina as opções. Tipos iniciais incluem IGBT, capacitor, resistor, transistor, placas de disparo/potência/controle, Fan/Cooler etc. Capacitor recebe Eletrolítico/Poliéster/Cerâmico/Filme; resistor e transistor têm subtipos de exemplo. Formatos já existentes PTH, SMD, TO-92, TO-220, TO-247, SOT-23; TO-263 é acrescentado.
- Nova aba **Tipos e formatos** para manter o mapa físico separado e simples. Código técnico imutável após criação para preservar vinculações existentes; nome de apresentação editável.
- Mapa: estantes com exatamente uma fileira de cinco posições; novas estantes `A`, `B` etc recebem endereços `A1` a `A5`, `B1` a `B5`. O código é um identificador interno imutável. Caixa `445` aparece como `Caixa 445`, gaveta idem; galerias disponíveis e tipos extras podem ser cadastrados nas configurações avançadas.
- As posições antigas e os registros já associados **não são renumerados** pela migration. Pode-se reatribuir os itens usando o formulário de edição, depois de revisão operacional.
- Etiquetas PDF utilizam nomes legíveis para os novos endereços físicos.
- Foto selecionada no novo cadastro é enviada após a criação do item; falha de foto é comunicada, sem recriar o item. É possível anexar foto ao editar ou nos detalhes. Fotos podem depender das permissões do navegador/câmera no dispositivo.
- Itens individuais continuam limitados a uma unidade; componentes por lote mantêm quantidade e mesma etiqueta nas movimentações.

## Arquivos alterados e novos

- `codigo-fonte/apps/api/app/inventory/models.py`: modelos de catálogo/subtipos.
- `codigo-fonte/apps/api/app/inventory/schemas.py`: contratos Pydantic.
- `codigo-fonte/apps/api/app/inventory/router.py`: catálogo CRUD, validações, estantes A1–A5, etiquetas.
- `codigo-fonte/apps/api/migrations/versions/20261026_03_inventory_catalog_shelves.py`: tabelas, FK, dados iniciais; preservação das categorias antigas.
- `codigo-fonte/apps/web/src/features/inventory/InventoryDashboard.tsx`: UX completa.
- `codigo-fonte/apps/web/src/features/inventory/inventory.css`: cartões grandes e tema azul escuro.
- `codigo-fonte/apps/api/tests/test_inventory_catalog_v6.py`: novos testes.
- `codigo-fonte/apps/api/tests/test_inventory_ux_purchase_contract.py`: contrato da nova organização.
- `INSTALAR_SENTICO_DEV.ps1`: aceita migrar de V5 para `20261026_03`.

## Testes realizados

- `pytest` focado Estoque, Compras, OS e contratos: **34 passed**.
- AST Python: aprovado.
- TSX: análise sintática via TypeScript `transpileModule`: aprovado.
- Alembic `heads`: `20261026_03 (head)`.
- Alembic `upgrade 20261026_02:20261026_03 --sql`: SQL PostgreSQL gerado.
- Pacotes ZIP: CRC/SHA256 conferidos.

**Não executados aqui:** Docker Desktop e PostgreSQL reais com migration aplicada; teste da câmera no hardware; build completo `tsc -b && vite build`; teste no navegador; suíte total de backend (coleta falhou sem dependência `psycopg` disponível na máquina de validação). Não autoriza deploy na VPS.

## Instalação local, sem perder dados

1. Recomenda-se testar primeiro em **cópia independente** da V5 com banco de desenvolvimento próprio. A pasta do código não armazena o volume PostgreSQL.
2. Para atualizar a **mesma instalação local**, fazer backup do volume PostgreSQL e uploads, guardar a pasta V5 e preservar `.env.dev`/nome de projeto/volumes; aplicar o ZIP de alterações somente na cópia V5 compatível.
3. Executar `INICIAR_SENTICO_GREEN.cmd` no ZIP completo, ou usar `INSTALAR_SENTICO_DEV.ps1` com Docker Desktop Linux iniciado. O instalador foi ajustado para a revisão V6. Não executar `down -v`, `volume prune` ou qualquer comando que apague volumes.
4. Homologar: criar estante A e verificar A1–A5; B e verificar B1–B5; criar caixa 445 e conferir rótulo, fotos, cadastro por série/lote, categorias/subtipos, Compras recebidas, retirada e devolução para OS, custo e etiquetas.
5. Ao apresentar erro, parar no primeiro e inspecionar o log: não tentar forçar migrations nem marcar cabeçalho Alembic manualmente.

## Aviso sobre dados históricos

Os endereços antigos `EST-XX-YY-ZZ` e demais códigos continuam válidos. O novo padrão A1–A5 aplica-se somente às estantes cadastradas na V6. O modelo de empresa continua no banco para não quebrar Compras/Financeiro; apenas o seletor não é mostrado na tela de cadastro do Estoque.
