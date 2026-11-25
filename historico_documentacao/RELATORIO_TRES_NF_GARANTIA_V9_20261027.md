# SÊNTICO ERP — Atualização V9: três notas fiscais de garantia por OS

## Objetivo
Cada OS possui três campos independentes e opcionais: NF de garantia 1, NF de garantia 2 e NF de garantia 3. Podem ser preenchidos em momentos diferentes, quando houver retorno posterior do equipamento. As NFs de entrada e saída permanecem independentes.

## Compatibilidade e persistência
A coluna já existente `laboratory_work_orders.warranty_invoice` permanece intacta e representa a NF de garantia 1. A migration `20261027_02` (após `20261027_01`) acrescenta exclusivamente `warranty_invoice_2` e `warranty_invoice_3`, ambos VARCHAR(80), opcionais e indexados para pesquisa. Os campos são transmitidos em criação, edição, listagem e consulta detalhada.

A pesquisa por texto no Laboratório consulta NF de garantia 1, 2 ou 3 junto com os demais critérios existentes, sem desativar empresa, mês, ano ou status. A tabela de OS exibe os valores preenchidos com identificação G1/G2/G3.

## Instalação local a partir da V8
1. Faça backup consistente do PostgreSQL, do volume de uploads e da pasta do projeto.
2. Para uma atualização incremental, aplique o ZIP `SOMENTE_ALTERACOES` na raiz da V8, respeitando os caminhos; ele contém também o instalador de mesma estrutura já ajustado para a nova revisão.
3. Preserve `.env.dev` e os volumes PostgreSQL e uploads. Não execute `docker compose down -v`.
4. Inicie com o Docker Desktop e `INICIAR_SENTICO_GREEN.cmd`. O instalador verifica o head `20261027_02` e aplica a migration pendente. O fluxo anterior de inicialização do Docker não foi substituído.
5. Confira uma OS antiga que já tinha NF de garantia 1, preencha NF de garantia 2 em outro momento, salve, reabra e pesquise por esse número usando filtros de mês/ano/status.
6. Repita com NF de garantia 3. Confirme que NF de entrada/saída e as demais garantias permaneceram corretas.

## Testes executados nesta entrega
- 40 testes de regressão selecionados aprovados, incluindo 4 testes novos específicos de três garantias.
- SQL PostgreSQL offline da migration gerado pelo Alembic com HEAD único `20261027_02`.
- Python compilado (sintaxe) e componentes TS/TSX analisados sintaticamente pelo parser TypeScript (0 erros).
- Integridade dos ZIPs aferida por teste CRC.
- Quatro testes de contrato pré-existentes apontam para `/web` (caminho do container Docker), indisponível neste ambiente isolado; não foram usados para alegar aprovação.

## Limitações
Não foi possível executar build completo do frontend com node_modules, nem homologar com um PostgreSQL real e navegador nesta sessão. Não publicar na VPS sem homologação local. Nenhuma alteração foi realizada na VPS ou nos volumes. O pacote inclui apenas código, migrations, documentação e instalador, sem dados ou credenciais reais.
