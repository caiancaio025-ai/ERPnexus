# Correção V11 — NFs normais e notas de garantia independentes

Data: 27/10/2026. Fonte: SÊNTICO V10 entregue anteriormente; Docker, Compose e regras de faturamento preservados.

## Regra implementada

- Cadastro principal da OS: `entry_invoice` = **NF de entrada**, `exit_invoice` = **NF de saída**.
- Seção separada **Garantia — retornos do equipamento**: `warranty_entry_invoice_1` e `warranty_exit_invoice_1`, e correspondentes pares 2 e 3.
- Todos os oito campos podem ser preenchidos em momentos distintos, editados e usados na pesquisa do Laboratório, que combina os outros filtros ativos.
- A listagem distingue NF normal e NFs de garantia, identificando G1/G2/G3.
- Os campos extras antigos da V10 `entry_invoice_2`, `entry_invoice_3`, `exit_invoice_2`, `exit_invoice_3` e os três campos genéricos V9 `warranty_invoice*` **não são apagados**. Seus valores antigos aparecem no bloco recolhido de histórico da OS quando houver dados. Não são copiados automaticamente para a garantia, pois sua classificação seria ambígua. O bloco de histórico é de consulta; uma correção de legado exige procedimento controlado.

## Banco de dados

- Migration incremental `20261027_04_separate_warranty_entry_exit_invoices.py`, dependente da revisão `20261027_03`.
- Cria 6 colunas opcionais com índices em `laboratory_work_orders`, sem remoção ou atualização de valores anteriores.
- O instalador local reconhece revisão existente V10 e atualiza até o novo head V11; não executa `down -v`.

## Arquivos alterados na base V10

- `codigo-fonte/apps/api/app/laboratory/models.py`
- `codigo-fonte/apps/api/app/laboratory/schemas.py`
- `codigo-fonte/apps/api/app/laboratory/service.py`
- `codigo-fonte/apps/api/app/laboratory/router.py`
- `codigo-fonte/apps/api/migrations/versions/20261027_04_separate_warranty_entry_exit_invoices.py` (novo)
- `codigo-fonte/apps/web/src/features/laboratory/types.ts`
- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `codigo-fonte/apps/api/tests/test_v11_normal_and_guarantee_invoices.py` (novo)
- `codigo-fonte/apps/api/tests/test_v10_three_entry_exit_invoices.py` (ajuste contrato visual V11)
- `INSTALAR_SENTICO_DEV.ps1`
- `LEIA_PRIMEIRO_INSTALACAO.md` e este relatório.

## Validações executadas

- 67 testes selecionados aprovados: NFs normais/garantia, compatibilidade V9/V10, Estoque, Compras, OS e custos.
- Sintaxe dos arquivos Python alterados: aprovada (AST).
- Parse e transpilação sintática de TS/TSX alterados: sem diagnóstico.
- Alembic head `20261027_04` e SQL offline específico da migration `20261027_03:20261027_04`: gerado com sucesso.
- Pacotes ZIP: manifestos SHA256 e teste CRC verificados.

## Limitações e homologação necessária

- A suíte completa não iniciou no ambiente de análise devido à dependência não instalada `psycopg`; testes com caminho de container `/web` não são executáveis fora do Docker sem adaptação.
- O build completo do frontend não foi executado (não há `node_modules` Vite no ambiente).
- A migration e a persistência ainda exigem validação num PostgreSQL real do Docker local, com backup antes da atualização.
- **Não foi alterada a VPS; não publicar pacote local sem eliminar credenciais e seed de desenvolvimento.**

## Roteiro mínimo local

1. Fazer backup real do volume PostgreSQL e dos uploads, preservando o `.env.dev` sem compartilhá-lo.
2. Atualizar a V10 com o ZIP de alterações. Aplicar migration V11 via instalador local.
3. Criar OS com NF de entrada e saída normais; preencher somente Garantia 2, salvar, reabrir; confirmar que todos os outros campos permaneceram intactos.
4. Pesquisar por cada uma das seis NFs de garantia, mantendo filtros de mês/ano/empresa/status ativos.
5. Abrir OS legada V9/V10 com dados preenchidos e confirmar histórico preservado.
6. Revalidar criação/edição da OS, orçamento, Compras e custo de peças.
