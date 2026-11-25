# SÊNTICO ERP — atualização V7 (26/10/2026)

## Origem e objetivo
Base **exclusivamente** na V6 funcional `SENTICO_GREEN_ESTOQUE_V6_CATALOGO_MAPA_20261026.zip`, **não** na V6 de alteração do inicializador/erro 1450. Nenhuma alteração foi aplicada à VPS, ao banco do usuário ou aos uploads. Instalação original (`INICIAR_SENTICO_GREEN.cmd` e `INSTALAR_SENTICO_DEV.ps1`) permanece byte a byte inalterada.

## Alterações de usabilidade

### Laboratório → OS → Materiais
- Dois caminhos visuais independentes: **Usar peça do estoque** e **Solicitar compra**. Apenas o formulário escolhido aparece, reduzindo congestionamento.
- Busca por nome, código interno, série e posição; seleção com saldo, localização, série e confirmação antes de baixar.
- A baixa continua pelo endpoint original `POST /inventory/items/{id}/issue`, com o mesmo recálculo do custo de peças na OS.
- A solicitação continua no endpoint original `POST /laboratory/work-orders/{id}/materials`, com prioridade, quantidade e observações preservadas.
- O planejamento do destino do Estoque na solicitação fica em seção expansível, opcional ao pedir e exigido no recebimento em Compras como antes.
- Histórico das solicitações permanece visível nos dois modos; histórico de retiradas e devoluções no modo Estoque.
- Painéis, campos e botões seguem o azul-escuro da aplicação; mensagens de confirmação legíveis.

### Estoque → Endereços / Mapa físico
- Criação simples de estantes, com a próxima letra sugerida automaticamente e cinco posições A1–A5, B1–B5 etc.
- Cadastro unitário de gavetas com número sugerido automaticamente; caixas e galerias mantidas.
- Botão explícito **Cadastrar gavetas 1–493** que gera em uma única transação apenas os endereços faltantes no banco. Não remove nem renumera os existentes; reconhece códigos antigos `GAVETA-001` como Gaveta 1 e evita duplicação lógica.
- Confirmação antes de cadastrar gavetas em massa, escolha de área quando houver mais de uma e retorno da quantidade efetivamente criada.
- Diretório de endereços pesquisável e paginado (40 registros/página), evitando 493 botões na mesma tela.
- Mapa separado em **Estantes**, **Gavetas 1–493** e **Caixas e outros**; gavetas paginadas e busca por número. Clique numa posição filtra os itens do endereço.
- As opções de layout de um local foram movidas para seção avançada, mantendo edição de nome e atividade simples.

## Arquivos alterados/criados
- `codigo-fonte/apps/api/app/inventory/router.py`: rota idempotente `POST /inventory/containers/batch-drawers?area_id=...` e validação de código único de gaveta.
- `codigo-fonte/apps/api/app/inventory/drawer_batch.py`: normalização e cálculo de gavetas faltantes.
- `codigo-fonte/apps/api/tests/test_inventory_drawer_batch_v7.py`: testes de idempotência, preenchimento incompleto, códigos com zero à esquerda, limites e contratos.
- `codigo-fonte/apps/web/src/features/inventory/InventoryDashboard.tsx`: cadastro e pesquisa de locais, integração com novo mapa e lote.
- `codigo-fonte/apps/web/src/features/inventory/InventoryPhysicalMap.tsx`: mapa visual simples e paginado.
- `codigo-fonte/apps/web/src/features/inventory/InventoryUsePanel.tsx`: apresentação da baixa na OS.
- `codigo-fonte/apps/web/src/features/inventory/inventory.css`: tema e endereçamento.
- `codigo-fonte/apps/web/src/features/laboratory/components/MaterialsPanel.tsx`: seletor das duas ações.
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`: apresentação do setor de Materiais.

## Compatibilidade e banco
- **Nenhuma nova migration**. A revisão Alembic permanece `20261026_03`.
- Os registros existentes, série, etiqueta, vínculo com a OS, fotos e movimentos não são modificados pelo pacote.
- A criação em massa **somente ocorre após clicar no botão e confirmar**. Ela acrescenta endereços novos, sem movimentar itens.
- O banco e uploads continuam em volumes persistentes Docker; o pacote não contém banco de produção ou senhas.

## Testes executados
- **66 testes pytest aprovados**, focados em Inventário, Compras, Materiais da OS, custos e regressões associadas; incluindo 6 testes V7.
- `compileall` do backend do Inventário concluído.
- Parse/transpilação TypeScript (TSX) com TypeScript 5.x global: 4 componentes verificados, sem erros sintáticos.
- Instalação: instalador V6 original comparado byte a byte, inalterado.
- ZIPs auditados quanto à lista de arquivos, CRC/SHA256 e ausência de `.env`/uploads.

## Limitações de homologação
- Não foi realizado build completo Vite nem teste visual real do navegador: o cache npm deste ambiente não contém a distribuição Vite (tentativa `npm ci --offline` retornou `ENOTCACHED`).
- Não foi exercitada a rota em PostgreSQL real neste ambiente; sua operação transacional deverá ser testada em Docker local.
- Não foram executados smoke tests completos no Docker Windows. Não classificar como homologado para produção antes desses testes.

## Instalação local segura
1. Faça backup da pasta local e **um backup consistente do banco** em uso antes de aplicar patch.
2. Para aplicar sobre a V6 **funcional**, use o ZIP de alterações e sobrescreva só seus arquivos em caminhos equivalentes; ou use o pacote completo numa pasta separada sem mudar o nome de projeto/volume do Docker.
3. Preserve o `.env.dev` e os volumes `sentico-dev-entrega_dev_postgres_data` e de uploads. Não use `docker compose down -v`.
4. Recrie/reinicie serviços pelo instalador original já funcional e abra o SÊNTICO.
5. Teste uma OS com retirada do Estoque, uma solicitação de compra, estantes A/B, e o cadastro idempotente das gavetas. Confira que A1–A5 e B1–B5 permanecem corretos e que Gaveta 1, 445 e 493 são pesquisáveis.
6. Execute o lote de gavetas novamente e confirme `created: 0`, sem saldo de itens alterado.
7. **Não implante na VPS** sem backup, validação visual e regressão em banco de homologação.
