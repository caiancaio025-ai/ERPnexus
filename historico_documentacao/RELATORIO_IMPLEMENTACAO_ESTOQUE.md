> DOCUMENTO HISTÓRICO (V1/V2). Para a versão atual de 26/10/2026, use `LEIA_PRIMEIRO_INSTALACAO.md` e `RELATORIO_AJUSTES_ESTOQUE_V3_20261026.md`.

# SÊNTICO ERP — Implementação do Estoque técnico (22/10/2026)

## Origem e segurança

Base: `SENTICO_GREEN_COMPLETO_ADM_PRECADASTRADO_20261022.zip`, da cópia local auditada. Alterações somente em desenvolvimento: **não houve acesso ou deploy na VPS**, nem importação de dados reais de produção. O instalador original foi atualizado para aceitar a nova revisão `20261022_01`.

## Entrega funcional

1. Menu Estoque (`/estoque`) deixa de ser placeholder e ganha interface de cadastro, pesquisa, mapa e configuração física.
2. Áreas físicas, tipos de locais **editáveis** (estante, gaveta, caixa, galeria, armário, prateleira, bancada e personalizados), recipientes com hierarquia e posições automáticas linha/coluna. Cada posição possui código único e o mapa mostra ocupação real. Mudanças de localização geram histórico com usuário e horário.
3. Cadastro de equipamento/peça **individual por número de série** (saldo 0 ou 1 após movimentações) ou de componente de consumo **por quantidade** (um código de lote permanece igual a cada baixa).
4. Identificador interno permanente `EST-########`, etiqueta PDF 40x40 com QR, série, descrição e posição; pesquisa por código, série, descrição, categoria ou endereço.
5. Fotos JPG/PNG/WEBP, com assinatura real de arquivo e limite 10 MB, armazenamento no volume persistente de uploads e acesso autenticado.
6. Registro imutável de entradas, saídas para OS e devoluções, com usuário, hora, quantidade e custo congelado na data da saída. Saldo impedido de ficar negativo; atualizações concorrentes bloqueiam a linha do item em transação PostgreSQL.
7. Aba **Laboratório → OS → Materiais → Retirar do estoque**: seleção por código/série/local, emissão da baixa e devolução parcial ou integral. Só permite vincular a empresas equivalentes da OS e do estoque.
8. Custo da OS passa a somar **compras concluídas já existentes** e **peças consumidas no estoque**, abatendo devoluções. Valores unitários restritos ao perfil Gestão/super_admin; técnicos veem apenas quantidade e endereço.
9. As migrations são **aditivas**; não alteram tabelas antigas além do recálculo do campo canônico `parts_cost`, quando há movimento ou alteração relevante.

## Exemplos de uso

- **IGBT serializado:** registrar `S/N QP-123`, quantidade 1; baixa na OS 321 torna saldo 0 e mantém o registro e etiqueta. Uma segunda baixa deve retornar erro HTTP 409. Devolução permite voltar a saldo 1.
- **Capacitor 470 µF:** registrar lote `EST-00000023`, quantidade 150 e custo unitário R$ 12,00. Retirar três para uma OS deixa 147, preservando o mesmo lote. O custo adicionado à OS é R$ 36,00; devolver uma peça remove R$ 12,00 do custo e deixa 148.

## Arquivos principais

- API: `apps/api/app/inventory/{models,schemas,service,router,label_pdf}.py`.
- Migration: `apps/api/migrations/versions/20261022_01_inventory.py`.
- Integração de custos: `apps/api/app/purchasing/material_service.py` e salvamento da OS em `apps/api/app/laboratory/router.py`.
- Frontend: `apps/web/src/features/inventory/{InventoryDashboard,InventoryUsePanel}.tsx` e `inventory.css`.
- Menu: `apps/web/src/app/router/AppRouter.tsx`.
- UI do Laboratório: `apps/web/src/features/laboratory/components/MaterialsPanel.tsx`.
- Testes: `apps/api/tests/test_inventory_stock_rules.py`.

## Testes executados e limites

- **51 testes aprovados** na seleção focada de Estoque, contratos de Laboratório, mapa e Comercial.
- SQL da nova migration gerado em modo offline PostgreSQL: **8 tabelas e 13 índices**; todas as instruções foram emitidas sem exceção.
- Sintaxe Python dos arquivos novos; análise sintática TypeScript/TSX dos cinco arquivos alterados: sem erros de parsing. Isso não substitui a checagem completa de tipos do TypeScript.
- A execução da suíte completa em ambiente de auditoria não foi homologada: `psycopg` indisponível para testes que inicializam a API; outros testes legados dependem de `/web` montado no Docker e de CSVs com dados financeiros reais que foram corretamente excluídos da entrega sanitizada. Na execução de diagnóstico, 283 testes passaram, 23 falharam por caminhos/dados históricos ausentes e 9 tiveram erro de coleta por falta do driver PostgreSQL.
- O build do frontend e integração HTTP com PostgreSQL **ainda não foram testados** neste ambiente, que não possui Docker Desktop e não concluiu download de dependências NPM. Realizar homologação local obrigatória.

## Como testar no computador Windows

1. Extraia o pacote completo novo **em pasta isolada**. Não copie o código novo diretamente sobre o volume de uma produção ou de outra instalação.
2. Abra Docker Desktop (containers Linux), execute `INICIAR_SENTICO_GREEN.cmd` na raiz, aguarde `SENTICO_DEV_INICIADO=OK`.
3. Confirme `docker compose --env-file .env.dev -f compose.dev.yml exec -T api alembic current` mostra `20261022_01`.
4. Acesse `http://127.0.0.1:5184/`, faça login com a conta de testes já configurada para desenvolvimento.
5. Em Estoque, crie uma área (ex.: ALM), uma estante 3×2, uma caixa e uma gaveta; verifique suas posições no mapa.
6. Cadastre um item por série e outro em lote; anexe fotos; imprima etiquetas.
7. Crie/abra uma OS da mesma empresa; na aba Materiais, retire uma unidade serializada e três componentes; valide saldos e custo na aba Financeiro com perfil Gestão; tente uma retirada a mais (deve falhar); devolva uma unidade do lote e confirme o estorno do custo.
8. Teste usuários sem acesso a valores; teste a tela em resoluções desktop e mobile. Execute regressões completas dentro do Docker antes de aceitar a feature.

### Atenções de implantação e integração

- **Não aplicar a migration na VPS** sem backup consistente, revisão, testes em clone de banco, homologação e janela aprovada.
- `parts_cost` continua sendo fonte canônica de custo de peça. Se a mesma peça for registrada ao mesmo tempo como **compra vinculada à OS** e **retirada do estoque**, o custo poderá ser contado duas vezes. Antes da integração operacional Compras→Estoque, definir o identificador da movimentação de recebimento vinculado à compra para contabilização única; não fazer baixa automática de compra neste pacote.
- Fotos dependem do volume persistente `dev_uploads`. Em produção, preservar volumes e garantir política de backup/restauração de fotos.
- O instalador local inclui login fictício `adm` / `123` **somente no modo de testes e com portas em loopback**. Jamais publicar esse ambiente na internet.
- Caso um cliente precise de exportação/auditoria fiscal de valor em estoque, planejar depois tratamento por custo médio/FIFO; esta versão mantém custo unitário cadastrado e custo histórico da saída.

### Reutilização de ambiente local existente

O launcher `INICIAR_SENTICO_GREEN.cmd` usa identidade Docker fixa `sentico-dev-entrega`; agora verifica a origem dos containers antes do `up`. Se outra pasta já for dona desse projeto Compose, o launcher **interrompe**, em vez de reutilizar silenciosamente o banco de outra versão. Para homologação paralela, use um projeto Docker independente e portas diferentes; não force a identidade antiga nem altere volumes manualmente.
