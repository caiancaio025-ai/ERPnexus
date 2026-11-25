> HISTÓRICO V2. Para a atualização de 26/10 use `RELATORIO_AJUSTES_ESTOQUE_V3_20261026.md` e o instalador V3.

# SÊNTICO — Estoque V2: interface, formatos e Compras → Estoque

**Base:** `SENTICO_GREEN_ESTOQUE_COMPLETO_20261022.zip`, somente para desenvolvimento/homologação local. **Revisão nova:** `20261022_02`, após `20261022_01`.

## Implementado

- Tema azul marinho compatível com o Laboratório. Remoção do fundo branco e reformulação de cartões, janelas, lista e mapa.
- Cadastro de local físico simplificado: Estante, Caixa e Gaveta como opções principais; nome, local superior opcional e quantidade de posições. Área padrão Almoxarifado criada apenas quando o banco ainda não possuir áreas. Tipos extras e administração de áreas permanecem disponíveis nas configurações avançadas.
- Posições continuam gerando códigos exclusivos e aparecendo no mapa; novos locais ganham posição automática distinta no mapa. Mudança de nome/posição fica no clique do local cadastrado.
- Cadastro de formatos/encapsulamentos por categoria, editáveis e expansíveis: resistores PTH/SMD, capacitores radial/axial/SMD, transistores TO-92/TO-220/TO-247/SOT-23/SOT-223 etc. Novo campo formato no item; o valor é validado no backend para a categoria.
- Equipamento individual por número de série continua representando uma unidade. O painel não oferece "Receber mais unidades" e a API também bloqueia recebimento manual adicional. A devolução de uma saída de OS continua possível e auditada.
- Componentes por quantidade preservam a mesma etiqueta enquanto diminui o saldo por OS ou aumenta por entrada manual.
- Compras → Estoque automático e transacional: pedido marcado **Entregue** (`PurchaseOrder.status=delivered`) ou solicitação marcada **Recebido** (`MaterialRequest.status=received`) gera entrada (lote por quantidade) com etiqueta `EST-...`, quantidade, custo e origem identificados. Repetir o mesmo evento não gera nova entrada; há UNIQUE de origem.
- Se solicitação informar exatamente o código de um pedido em `purchase_reference` e produto, empresa, quantidade e custo coincidirem, a mesma movimentação de estoque é vinculada às duas origens, evitando dupla entrada. Se houver divergência, o sistema recusa o vínculo para revisão, sem adivinhar.
- Custo da OS: pedidos de compra gerais não alteram diretamente o custo da OS; uma solicitação de material que entrou no Estoque deixa de ser contabilizada como custo direto da solicitação. A retirada física pelo técnico compõe o custo da OS com o custo histórico. Devoluções subtraem o custo. Relatório de produtividade reflete entradas diretas e saídas/devoluções do Estoque separadamente.
- Edição/exclusão de compras já recebidas não pode modificar arbitrariamente produto, quantidade, valor, empresa ou estado físico; exige tratamento auditado para não corromper saldos.

## Observações e regras operacionais

1. O modelo de Compras não identifica números de série de cada peça adquirida. Recebimento automático cria **lote por quantidade**, sem inventar número de série; equipamentos individuais devem ser cadastrados com sua série explícita no Estoque. A série existente em `PurchaseOrder.equipment_serial` pertence ao equipamento atendido pela OS e **não** deve ser usada como série da peça comprada.
2. Compras por `PurchaseOrder` e por `MaterialRequest` só são conciliadas automaticamente quando a referência é explícita e os dados batem; se a mesma compra for cadastrada duas vezes sem vinculação, não existe evidência suficiente para deduplicação automática. Conferir processos de Compras antes do uso real.
3. O histórico de compras não é migrado retroativamente: apenas recebimentos **novos** criados a partir desta versão passam pelo fluxo automático. Para antigos, exigir projeto específico de conciliação.
4. Não há exclusão automática de lotes/etiquetas ao esgotar o saldo.
5. Mudanças de estado de compra já recebida ou cancelamentos após recebimento físico exigem rotina de estorno auditado (não implementada nesta etapa); a API bloqueia alterações destrutivas.
6. Por segurança, nenhum dump de produção, foto de cliente ou segredo real está incluído.
7. Login fictício local `adm/123` permanece exclusivamente no Compose de desenvolvimento, **nunca utilizar na VPS**.

## Homologação local obrigatória

- Abrir o Docker Desktop (Linux containers). Extrair o ZIP completo em **uma pasta nova** para testar sem substituir a anterior.
- Executar `INICIAR_SENTICO_GREEN.cmd`. O instalador deve validar a revisão `20261022_02`; quando a revisão do banco estiver em `20261022_01`, aplicar `alembic upgrade head` de forma aditiva, sem apagar os volumes.
- Login no `http://127.0.0.1:5184/`; abrir Estoque e conferir o tema azul; criar estante, caixa, gaveta e um tipo extra; imprimir etiqueta, visualizar mapa e testar alteração de local.
- Criar resistor SMD com 100 unidades; baixar 3 em uma OS e conferir saldo 97 e mesmo código; devolver 2 e conferir saldo 99 e custo da OS.
- Criar equipamento individual serializado; verificar ausência do botão "receber mais unidades"; tentar POST de entrada unitária e confirmar HTTP 409; devolver somente mediante saída original de OS.
- Criar formato de transistor novo e aplicar ao cadastro; formato inválido para categoria deve ser rejeitado.
- Em Compras, criar pedido com status em transporte, depois alterar para Entregue: deve surgir **uma** entrada no estoque; salvar novamente deve manter a única entrada. Confirmar etiqueta, histórico e custo.
- Em solicitações de Compras, alterar para Recebido; observar entrada no estoque; registrar retirada via OS e conferir que o custo não duplica. Quando houver pedido e solicitação referentes ao mesmo recebimento, colocar o código real do pedido em `purchase_reference` antes da confirmação e verificar conciliação.
- Validar permissões de valores (técnico não visualiza custo), fotos e relatórios da OS.
- Rodar regressão completa, build frontend e testes integrados no navegador, em ambiente Docker operacional.

## Testes executados aqui

- **302 testes aprovados** em suite não dependente de serviços adicionais, no diretório `apps/api`.
- Nova suíte de testes para recebimento automático, idempotência, vinculação de Compras, formato/categoria e segurança do item serializado.
- Migration `20261022_02` gerou SQL PostgreSQL válido em modo offline via Alembic.
- Verificação de sintaxe Python e parse do componente TSX (sem erros sintáticos).

**Não validados neste ambiente:** build Vite/TypeScript integral (dependências npm ausentes na sandbox), Docker Desktop real/PostgreSQL em execução, login navegador; uma parcela da suíte de testes depende de `psycopg`, `/web` montado no container ou de dados CSV de conciliação propositalmente excluídos por conterem informações reais. Não implantar na VPS antes de executar esses testes.
