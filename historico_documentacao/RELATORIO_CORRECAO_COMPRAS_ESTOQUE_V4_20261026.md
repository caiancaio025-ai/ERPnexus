# SÊNTICO Green — Estoque V4 | Solicitações avulsas e materiais da OS

**Base:** pacote Green Estoque V3 de 26/10/2026. **Ambiente:** desenvolvimento local, não VPS. **Migration:** `20261026_02` (após `20261026_01`).

## Problema reproduzido por inspeção

Na V3, `PurchaseOrder` persistia `inventory_destination`, `inventory_item_id` e demais campos, enquanto `MaterialRequest` não possuía tais colunas. Por isso, os formulários de solicitação avulsa e do Laboratório não mostravam a vinculação ao Estoque, e o recebimento de solicitações criava automaticamente um item novo por descrição. Isso impedia a soma de novas unidades a um SKU preexistente e criava registros desnecessários.

## Mudanças implementadas

- **Pedido de compra**: mantém a escolha de destino existente da V3, lançando estoque apenas ao marcar **Entregue**.
- **Solicitação avulsa**: apresenta a seleção do Estoque no formulário de criação (opcional) e no editor de acompanhamento, permitindo mudar até a chegada.
- **Solicitação para OS do Laboratório**: mesma escolha na aba Materiais, com busca de cadastro existente ou planejamento de item novo.
- **Solicitação recebida**: ao avançar para **Recebido**, exige destino de estoque; soma ao saldo do item existente (somente itens de quantidade) com custo médio, ou cria novo item e etiqueta sem local obrigatório.
- **Equipamentos individualizados**: quantidade 1 e série informada ao receber. Não adiciona quantidade a um item serializado existente.
- **Idempotência**: status e registro de movimentação usam a mesma transação da origem; a chave única `material_request_id` impede dois recebimentos da mesma solicitação. Se a solicitação estiver ligada explicitamente a um pedido entregue, pode compartilhar a mesma movimentação quando empresa, quantidade, preço e item forem compatíveis.
- **Custo de peças da OS**: apenas a retirada física `issue` entra no custo quando houve entrada no estoque. O recebimento de compra não conta duas vezes.
- **Recebimentos históricos já marcados como recebidos mas sem movimentação**: exigem conciliação manual, não são relançados ao salvar a solicitação.
- **Localização**: itens novos seguem sem posição. A estante, gaveta ou caixa pode ser definida depois na aba Estoque.

## Instalação local

1. Faça backup de sua pasta da V3 e do banco local de testes (se houver dados a preservar). Para testar isoladamente, extraia o **ZIP completo numa pasta nova**, certificando-se de que não está reutilizando o mesmo projeto Compose de outra versão.
2. Abra o Docker Desktop com Linux Engine.
3. Execute `INICIAR_SENTICO_GREEN.cmd` na raiz do pacote. O instalador valida o banco local e aplica o Alembic até `20261026_02` sem comandos de exclusão de volumes.
4. Acesse `http://localhost:5184`. O usuário de testes, quando inicializado pelo pacote, é `adm` / `123`, **exclusivo para desenvolvimento local**.
5. Se estiver atualizando a instalação V3 com o ZIP de alterações, sobreponha somente os arquivos do patch na pasta equivalente e **preserve `.env.dev` e volumes**. Faça `docker compose --env-file .env.dev -f compose.dev.yml up -d --build` e, depois de verificar a cópia de segurança e a revisão, rode `docker compose --env-file .env.dev -f compose.dev.yml exec -T api alembic upgrade head`.

## Cenários de homologação

1. Criar **solicitação avulsa** sem destino, avançar até **Comprado**, escolher **Somar a item existente** antes de **Recebido**; confirmar que saldo antigo mais quantidade corresponde ao novo saldo e a etiqueta não mudou.
2. Reabrir a solicitação já recebida; verificar que não cria outra entrada ou muda os valores do histórico.
3. Solicitar um material na **OS do Laboratório**, pesquisar o saldo antes da solicitação, escolher novo item e depois confirmar o recebimento em Compras; verificar nova etiqueta e localização pendente.
4. Testar uma solicitação de componente com 15 unidades e outra com 20 unidades para o mesmo SKU; o saldo deve aumentar 35, sem duplicar itens. Modo individual com quantidade 2 deve ser rejeitado.
5. Testar pedido comum **Entregue**, garantindo que sua entrada continua funcionando.
6. Quando pedido e solicitação representam a **mesma compra física**, preencher `purchase_reference` com o código real do pedido e usar destino compatível em ambos; conferir uma única entrada. Se houver divergência, corrigir as referências antes de receber; não forçar soma automática.
7. Após entrada, técnico retira 2 unidades para uma OS; verificar saldo e custo, depois estornar uma unidade; conferir histórico e custo recalculado.
8. Verificar permissões para usuários que não podem ver valores de compra e para técnicos de laboratório que não acessam Compras.

## Evidências e limites da entrega

- Regra de estoque e contratos: **29 testes selecionados aprovados**, incluindo testes anteriores.
- Arquivos Python compilados com `compileall`; 5 arquivos TSX/TS analisados com parser TypeScript, sem erros sintáticos.
- A suíte integral `pytest` foi iniciada, mas a coleta foi interrompida por ausência de `psycopg` neste ambiente de validação. Isso **não** constitui aprovação da suíte completa.
- Não houve acesso a Docker/PostgreSQL real neste ambiente; migrations não foram aplicadas a banco verdadeiro; build completo do Vite não foi executado. **V4 requer homologação local antes de qualquer implantação.**
- Recebimento **parcial** ainda não está coberto pelo fluxo de status inteiro. Não misturar pedido e solicitação da mesma compra sem vínculo explícito; não há reconciliação automática por nomes parecidos.

## Arquivos-chave alterados

`apps/api/app/purchasing/material_models.py`, `material_schemas.py`, `material_service.py`, `router.py`; `apps/api/app/laboratory/router.py`; `apps/api/app/inventory/purchase_cycle.py`; migration `20261026_02_material_request_inventory_target.py`; painel `apps/web/src/features/purchasing/MaterialRequestsPanel.tsx`, painel `apps/web/src/features/laboratory/components/MaterialsPanel.tsx`, componente compartilhado `apps/web/src/features/inventory/PurchaseStockDestination.tsx` e CSS, ambos os `types.ts`, testes, instalador e documentação.

## Arquivos incluídos no patch V4

- `INSTALAR_SENTICO_DEV.ps1`
- `LEIA_PRIMEIRO_INSTALACAO.md`
- `codigo-fonte/README_DEV_ENTREGA.md`
- `codigo-fonte/apps/api/app/inventory/purchase_cycle.py`
- `codigo-fonte/apps/api/app/laboratory/router.py`
- `codigo-fonte/apps/api/app/purchasing/material_models.py`
- `codigo-fonte/apps/api/app/purchasing/material_schemas.py`
- `codigo-fonte/apps/api/app/purchasing/material_service.py`
- `codigo-fonte/apps/api/app/purchasing/router.py`
- `codigo-fonte/apps/api/migrations/versions/20261026_02_material_request_inventory_target.py`
- `codigo-fonte/apps/api/tests/test_material_request_inventory_unification.py`
- `codigo-fonte/apps/web/src/features/inventory/PurchaseStockDestination.tsx`
- `codigo-fonte/apps/web/src/features/inventory/purchaseStockDestination.css`
- `codigo-fonte/apps/web/src/features/laboratory/components/MaterialsPanel.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/types.ts`
- `codigo-fonte/apps/web/src/features/purchasing/MaterialRequestsPanel.tsx`
- `codigo-fonte/apps/web/src/features/purchasing/types.ts`
