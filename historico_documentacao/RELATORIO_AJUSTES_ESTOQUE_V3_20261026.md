# SÊNTICO Green — Estoque V3 / Compras vinculadas — 26/10/2026

## Solicitação implementada

- O nome comercial do pedido continua separado do nome técnico do item de estoque.
- O pedido pode ser salvo em andamento sem preencher destino de estoque, inclusive com categoria e formato em branco.
- Pesquisa preventiva no cadastro de Compras pelo nome, etiqueta e número de série, exibindo quantidade disponível na **mesma empresa**. A quantidade é disponibilidade bruta, não saldo reservado para OS.
- No recebimento (status **Entregue**), é obrigatório decidir destino: **item existente** (somente lotes `bulk`) ou **item novo** (`bulk`/`serialized`).
- Em item existente, o sistema **mantém a etiqueta** e **soma a quantidade**, registra movimentação única por pedido, conserva o custo unitário histórico e atualiza o custo médio da posição para futuras saídas.
- Em item novo, pode alterar o nome técnico, categoria, formato, e escolher lote ou número de série. Item individual exige quantidade 1 e série única na empresa.
- Sem posição obrigatória no recebimento: novo item fica sem slot até a equipe guardá-lo no mapa do Estoque. Um item existente mantém sua posição.
- O fluxo de solicitação de materiais anterior continua compatível: compartilhamento de entrada vinculada por referência do pedido exige conferência de empresa, quantidade e custo. Se houver divergência a operação é bloqueada.
- O custo da OS continua vindo das retiradas de estoque conforme implementação V2; o fluxo antigo evita contar novamente pedidos de materiais já recebidos no estoque.

## Implementação

- Migration incremental `apps/api/migrations/versions/20261026_01_purchase_inventory_target.py` (após `20261022_02`), sem alteração retroativa dos pedidos existentes. Destinos antigos ficam `NULL`.
- Models e contratos de pedido ampliados com `inventory_destination`, `inventory_item_id`, `inventory_name`, `inventory_mode`, `inventory_serial`, `inventory_category`, `inventory_format_id`.
- Consulta segura de estoque em `GET /api/purchasing/stock-options?company_code=...&search=...`, acessível aos usuários do módulo Compras, sem preços.
- Recebimento em transação única com travamento do item de lote, verificação de empresa, estado, idempotência por origem e custo médio.
- O destino do estoque não pode ser alterado depois de uma entrada registrada sem estorno auditado. Pedidos antigos da V2 que já tinham sido recebidos, com campos novos `NULL`, podem continuar tendo dados não físicos editados sem exigir novo destino nem duplicar o recebimento.
- UI integrada em `PurchasingDashboard.tsx`, CSS azul em `purchasing.css` e tipos em `types.ts`.
- Instalador de desenvolvimento atualizado para exigir revisão `20261026_01`; mantém a criação do administrador fictício.

## Garantias / limitações

- **Não** houve publicação na VPS, alteração de produção ou importação de dados reais.
- Testes focados SQLite: **29 aprovados**, incluindo saldo +5 em item existente, média de custo, idempotência, controle por série, rejeição de outra empresa e compatibilidade anterior.
- 177+ arquivos Python: sintaxe verificada por `ast.parse`; TSX validado com parser/transpilador TypeScript instalado globalmente.
- PostgreSQL real, build Vite e inspeção funcional da UI no navegador: **não executados** nesta infraestrutura. `npm ci --offline` falhou pois não havia cache de `vite@8.1.4`; suíte total exige `psycopg` ausente na máquina de auditoria. **Homologação local obrigatória** antes de deploy.
- Esta entrega trata o cadastro de **pedidos de compra**; solicitações avulsas de materiais mantêm a automação V2 de recebimento em lote, e somente pedidos vinculados podem compartilhar entrada. Não assumir que duas operações comerciais distintas são a mesma compra.
- Cada pedido representa uma linha/um tipo de peça no estoque. Recebimentos parciais e uma compra contendo múltiplos SKUs distintos exigem fluxo adicional futuro e não foram implementados neste patch.
- A consulta de saldo não desconta reservas técnicas porque o módulo atual não tem reserva; conferir disponibilidade efetiva antes de dispensar a compra.

## Homologação sugerida

1. Em pasta local de teste isolada, `docker compose ... up -d --build`; confirmar migrations até `20261026_01`.
2. Criar pedido com descrição comercial e sem destino, salvar, editar e confirmar que a descrição permanece independente.
3. Pesquisar componente com saldo 10 e escolher "Somar ao existente"; ao entregar 5, conferir saldo 15, **mesma etiqueta**, movimentação com referência e custo médio.
4. Salvar pedido já entregue novamente e confirmar saldo 15, sem segunda entrada.
5. Comprar um equipamento individual, configurar quantidade 1 e número de série; entregar, localizar a nova etiqueta e verificar localização pendente.
6. Rejeitar entrega de equipamento individual quantidade 2 e vinculação a item de outra empresa; conferir ausência de lançamentos parciais.
7. Validar compra associada a solicitação recebida, sem dupla entrada, ou bloqueio explícito em caso de divergência.
8. Dar baixa na OS pela aba Materiais, validar custo e movimento de retirada, depois devolver e conferir saldo.
9. Realizar testes de regressão em Financeiro, Laboratório, Compras e permissões.

## Implantação

**Somente local.** Não atualizar a VPS durante testes. Não remover volumes nem recriar o banco. Aprovar build, migração PostgreSQL real, regressão e backup antes de planejar release Blue/Green.
