# SÊNTICO ERP V13 — Etiquetas com código curto

**Base:** V12 de Estoque com câmera; nenhuma modificação aplicada à VPS.

## Comportamento
- Cadastro manual e entradas automáticas de Compras geram `EST-01` a `EST-09`, `EST-10`, `EST-11`, `EST-100` etc.
- O número de série original do fabricante **não é alterado**.
- A migration `20261027_05`, que sucede `20261027_04`, converte os códigos EST antigos que correspondem ao ID do registro, sem alterar movimentações ou saldos. Exemplo: `EST-00000001` -> `EST-01`; `EST-00000100` -> `EST-100`.
- Os códigos físicos anteriormente impressos em QR/etiquetas podem continuar sendo **pesquisados pelo número antigo** no Estoque, Compras e seleção de peças do Laboratório. É recomendável reimprimir etiquetas físicas para refletir o código oficial atualizado.
- Entradas automatizadas em itens existentes conservam o código oficial do item, agora curto após migration.
- Registros com código personalizado ou código que não representa o ID do item ficam intactos e podem exigir revisão específica.

## Modificações
- `apps/api/app/inventory/stock_codes.py`: gerador e normalizador.
- `apps/api/app/inventory/router.py`: criação manual e pesquisa de etiquetas antigas.
- `apps/api/app/inventory/purchase_cycle.py`: criação automática a partir de Compras.
- `apps/api/app/purchasing/router.py`: pesquisa no seletor de estoque.
- `apps/api/migrations/versions/20261027_05_short_inventory_codes.py`: migration incremental.
- `apps/web/src/features/inventory/stockCode.ts`: compatibilidade local com etiquetas anteriores.
- `apps/web/src/features/inventory/InventoryDashboard.tsx`, `InventoryUsePanel.tsx`, `PurchaseStockDestination.tsx`: pesquisa e placeholders.
- `INSTALAR_SENTICO_DEV.ps1`: reconhecimento do head Alembic `20261027_05` (sem modificar configuração Compose).
- `apps/api/tests/test_inventory_short_codes.py`: cenários novos.
- `apps/api/tests/test_inventory_catalog_v6.py`: ajusta teste antigo incompatível com a câmera real adicionada na V12.

## Testes executados
- 66 testes focados de Estoque, Compras, solicitações e pesquisa aprovados com pytest.
- Compilação sintática Python e análise de sintaxe TypeScript para os quatro arquivos TS/TSX envolvidos aprovadas.
- `alembic heads`: confirmou `20261027_05 (head)`.
- Alembic gerou SQL PostgreSQL offline da migration `20261027_04 -> 20261027_05`.
- Integridade CRC e hash SHA256 dos pacotes conferida.

**Não homologado neste ambiente:** execução real da migration em PostgreSQL, build completo do frontend e teste de interface com câmera/Docker no Windows.

## Aplicação local segura
1. Efetue backup do PostgreSQL e dos uploads e conserve a V12 até concluir a homologação.
2. Use o ZIP de alterações por cima da V12 na mesma estrutura; não sobrescreva nem envie `.env.dev`.
3. Mantenha volumes Docker existentes. Jamais execute `docker compose down -v`.
4. Execute o instalador da própria V13, que reconhecerá a nova revision e migrará o banco local.
5. Confirme criação manual, criação via Compras, consulta por etiqueta antiga e nova, impressão PDF e saída/estorno na OS.
6. **Não publique na VPS** até validar migrations em cópia do banco e criar um backup restaurável.

Observação: o prefixo `EST-` é código interno do estoque, não o número de série do equipamento.
