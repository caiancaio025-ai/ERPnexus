# SÊNTICO ERP V14 — Patrimônio locado, mapa do estoque e documentos do cliente

Data: 28/10/2026. Base: **V13 EST curto**, sem mudanças no Compose e mantendo o instalador de desenvolvimento original com atualização apenas da revisão Alembic.

## 1. Etiqueta patrimonial com cliente da locação

- Campo persistente novo `commercial_equipment.rental_customer_id`, FK para `laboratory_customers`, com `ON DELETE SET NULL`.
- Na edição de Patrimônio (módulo Comercial), status **Locado** exige selecionar cliente ativo da mesma empresa; outros status não aceitam vínculo de locação.
- Etiqueta patrimonial em PDF 40×40 mm exibe **CLIENTE: nome fantasia ou razão social** apenas quando o patrimônio está Locado e tem vínculo válido. Mantém identificação, série e QR. Nomes extensos podem ser abreviados visualmente por limite físico da etiqueta (o vínculo completo fica no banco).
- Não foi feito vínculo automático com um orçamento antigo: orçamento não prova entrega/locação vigente.
- Patrimônios já locados sem vínculo antes da atualização precisarão ter o cliente selecionado na ficha antes da etiqueta exibir o nome.

## 2. Mapa físico e remoção controlada de endereços

- Abas do mapa: **Estantes**, **Gavetas 1–493**, **Caixas**, **Galerias**, **Outros**. O tipo legado `galeia` é reconhecido em Galerias.
- Na aba Endereços, o modal de edição traz **Excluir local**, e as configurações avançadas permitem excluir área vazia ou tipos adicionais não utilizados.
- Exclusão física: bloqueia local com sublocal, peça vinculada (mesmo sem saldo), ou histórico de deslocamento, incluindo posições anteriores e novas. Bloqueia área com local e tipo em uso. Tipos-padrão são protegidos contra exclusão. Nenhuma migração de inventário foi necessária.
- Em locais com histórico, mantém-se a opção de **inativar**, preservando rastreabilidade e integridade das FKs. Não existe exclusão forçada/cascata de peças.

## 3. Pesquisa de documentos dos clientes

- Barra de pesquisa com texto geral, categoria e data exata de emissão, além de botão Limpar filtros e contador de resultados.
- Busca no backend **antes da paginação**, combinando cliente, referência, nome original, observações, categoria e data de emissão (ISO ou seletor de data).
- Cards/listas destacam a categoria e observação, com interface responsiva e paleta azul escuro.
- A pesquisa não se limita aos primeiros 50 documentos, mantendo paginação e filtros combinados.

## 4. Banco, migrations, instalador

- Nova migration **`20261028_01`**, encadeada em `20261027_05`. Acrescenta apenas coluna, FK e índice no patrimônio comercial. Não deleta dados de estoque ou do cliente.
- O instalador local da V13 teve **somente os checkpoints Alembic** atualizados para `20261028_01`; o processo Docker/build não foi reescrito.
- Este pacote **não contém `.env.dev`, banco real, upload real, ou credenciais de produção**. Há um usuário de testes fictício no projeto, por isso **NÃO publicar o ZIP de desenvolvimento diretamente na VPS**.
- Antes de aplicar: backup PostgreSQL e uploads e cópia do projeto. Não usar `docker compose down -v`.

## 5. Testes executados no ambiente de geração

- **78 testes selecionados aprovados** na regressão de patrimônio, documentos, estoque e compras/etiquetas.
- Síntaxe Python validada; **5 arquivos TS/TSX alterados** transpilaram sem erros sintáticos no TypeScript global.
- Alembic `20261027_05:head --sql` produziu SQL PostgreSQL para a nova migration.
- PDF patrimonial de teste renderizado e conferido visualmente: QR, identificação, cliente e espaçamento.
- Arquivos ZIP comparados à base V13 e verificados por CRC/SHA256 após empacotamento.

### Pendente para homologação real

- Aplicar migration em **PostgreSQL real no Docker local** e inspecionar os dados existentes.
- Executar **build integral da Web** com dependências do projeto, testes end-to-end no navegador e uso de câmera/etiqueta na impressora real, se aplicável.
- Exercitar exclusão de endereços com referências reais, verificando mensagens de bloqueio e integridade.
- Não foi realizada alteração na VPS.

## 6. Roteiro rápido

1. No Comercial, edite um patrimônio, marque **Locado**, selecione o cliente certo, salve e imprima etiqueta; verifique nome e QR.
2. Volte o patrimônio a **Disponível**; confira que não aparece o cliente na etiqueta.
3. No Estoque, abra Mapa físico e confira as cinco guias. Crie uma caixa de testes, exclua-a; confirme que local usado/histórico não exclui.
4. Em Clientes → Documentos, pesquise uma referência antiga, filtre categoria, informe a data e remova filtros.
5. Verifique clientes, movimentações, OS e compras já cadastrados após a migration.
