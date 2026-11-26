# V48 — OS no próprio faturamento e entrada de Compras no Estoque

Correção de **26/11/2026**, identificada como **`v48-20261126-faturamento-estoque`**. O banco passa à revisão **`20261126_04`**. A versão principal continua sendo 48.

## Adicionar várias OS na tela de faturamento

A inclusão acontece no formulário do **Financeiro**, no quadro **Ordens de serviço do faturamento**, tanto em **Nova receita** quanto ao abrir uma receita já existente.

1. Abra a receita ou clique em **Nova receita**.
2. Em **Buscar Ordem de Serviço**, digite o número da OS, o cliente ou a série e clique no resultado para adicionar.
3. Repita a busca para incluir os outros equipamentos do mesmo cliente e empresa.
4. Confira o total da receita e preencha **Valor atribuído — OS-…** em cada cartão. O botão **Dividir total entre as OS** distribui o total igualmente, ajustando os centavos.
5. Clique em **Salvar alterações**, **Salvar lançamento** ou **Salvar N parcelas**, conforme a tela aberta.

Todas as OS pertencem à mesma receita ou obrigação financeira. Adicionar ou remover vínculos conserva o valor existente; o rateio precisa somar o total. Cada cartão oferece os links **Ver orçamento da OS** e **Ver valor aprovado**. Eles abrem outra aba para manter a edição em andamento.

### Receita existente e parcelamento

Ao editar uma receita, o sistema conserva seu identificador, documentos, histórico e pagamentos. A troca dos vínculos não recria o lançamento.

Ao editar uma parcela, os vínculos e o rateio correspondem ao **total de todas as parcelas da obrigação**. O campo **Valor da parcela** continua representando somente a parcela aberta. A tela identifica os dois valores; a inclusão de uma OS preserva o cronograma e os identificadores das parcelas.

Os vínculos ficam protegidos quando qualquer parcela já possui baixa ou competência fechada. O motivo aparece na própria tela; alterações documentais permitidas continuam disponíveis. A exclusão ou o cancelamento de uma OS também respeitam a existência de receitas compartilhadas.

As consultas de recebíveis e os relatórios atribuem a cada OS apenas a sua participação no faturamento. O total financeiro é contabilizado uma vez. A edição verifica versões, e a perda da resposta de uma gravação é conferida por leitura antes de considerar a operação inconclusiva.

Limites: até **50 OS** do mesmo cadastro de cliente e empresa, até **60 parcelas na interface**. Valores são calculados em centavos. Exigências de faturamento e saldo aprovado continuam sendo conferidos quando uma OS é incluída ou tem sua participação aumentada.

## Laboratório sem caixas de seleção de OS

As caixas de seleção e a barra **Faturar selecionadas** foram retiradas da lista do Laboratório.

Para reunir equipamentos em um orçamento, abra **Orçamentos conjuntos → Novo orçamento conjunto**. Busque e adicione as OS dentro dessa janela e clique em **Criar orçamento com N OS**. O mesmo botão está disponível no histórico da aba **Orçamento** da OS.

O orçamento conjunto conserva os recursos de rascunho, prévia, emissão de um PDF único e histórico de revisões. Cada equipamento mantém sua OS, sua série e seu valor no documento.

## Compras com os mesmos campos do cadastro avulso

O menu **Destino do material** permanece no quadro **Como entra no Estoque?**, com as opções de definir depois, somar a um item existente ou cadastrar um novo item.

Ao escolher **Cadastrar novo item com etiqueta**, o formulário usa o mesmo componente visual do cadastro avulso do Estoque:

- **Controle:** item por quantidade ou item individual com código automático.
- **Nome do item** e **Tipo de componente**, escolhido no catálogo.
- **Posição física**, com busca por estante, caixa, gaveta ou código; pode ficar sem localização.
- **Unidade** e **Descrição**.
- Em **Mais detalhes do item**: subtipo, formato/encapsulamento, fabricante e modelo.
- **Série do fabricante opcional**, quando há uma unidade.

A quantidade e o custo vêm da compra. No controle individual, uma compra de dez unidades gera dez cadastros de quantidade 1, cada um com seu código `EST-*`. O sistema não exige que o operador transforme a compra em dez solicitações nem inventa séries de fabricante. Se necessário, as séries reais podem ser preenchidas posteriormente no Estoque.

Se uma série real tiver sido informada e a quantidade for alterada para várias unidades, o valor permanece visível. O operador pode limpá-lo para usar os códigos automáticos e informar as séries depois; uma única série não é replicada silenciosamente para todos os itens.

### Salvar, reabrir e receber

**Salvar dados sem mudar status** guarda o planejamento e os detalhes do item. A quantidade entra fisicamente no estoque somente ao confirmar **Recebido** ou **Entregue**, conforme a compra.

Os dados reaparecem ao reabrir a solicitação ou pedido. No recebimento, os detalhes e a posição são aplicados a cada unidade, com registro de movimentação. Repetir a confirmação não duplica a entrada. Pedidos e solicitações vinculados compartilham a mesma origem física.

Uma solicitação antiga já marcada como **Comprado**, mas com custo nulo, pode salvar os dados do estoque e receber sem exigir novamente a transição de compra. A exigência de custo válido permanece na passagem inicial para **Comprado**.

Depois de receber, os campos físicos ficam protegidos na compra. Correções de nome, descrição, série e posição por unidade são feitas no Estoque. Registros antigos com vínculos de catálogo hoje inativos continuam podendo receber correções que preservem esses vínculos.

O recebimento individual aceita até **1.000 unidades** por operação. O cadastro por quantidade mantém o saldo em um único item.

## Atualizar a instalação da Hostinger

No terminal do servidor, como root:

```bash
cd /opt/sentico-green &&
git pull --ff-only origin main &&
bash infra/vps/atualizar.sh
```

O atualizador aceita as revisões `20261123_02` e `20261126_01` a `20261126_04`. Faz backup, ensaia as migrações em uma cópia restaurada, confere as restrições e a preservação do estoque e só então aplica as imagens.

Além da versão 48, verifica a identificação exata da API e os arquivos servidos da interface. O resultado esperado inclui:

```text
SENTICO_V48_ATUALIZADO=OK
REVISAO=v48-20261126-faturamento-estoque
```

Depois, use **Ctrl+F5** no navegador. O endpoint `/api/health/version` informa a mesma revisão. Os textos antigos de série obrigatória e quantidade igual a 1 no formulário de compra não fazem parte desta interface.

A migração `20261126_03` adiciona os vínculos de rateio e as versões financeiras. A `20261126_04` acrescenta os detalhes planejados de estoque em pedidos e solicitações. Vínculos singulares, receitas e dados anteriores continuam preservados; as migrações não refazem faturamentos antigos.

## Validação

| Verificação | Resultado |
| --- | --- |
| API, instalador, migrações e desempenho em PostgreSQL 17.12 | 779 aprovados; 7 não executados por dependerem de manifestos privados de conciliação ausentes |
| Atualizador da VPS | 125 aprovados |
| Inicializador do teste local, com PostgreSQL nativo | 17 aprovados |
| Lógica da interface | 39 testes Node e 20 verificações V41 aprovados |
| Navegador com API e banco reais | 10 cenários de Compras/Estoque e 11 de Financeiro/Laboratório aprovados |
| Navegador com API controlada e React StrictMode | 10 cenários de Financeiro e 7 de orçamento/NF aprovados |
| Compilação TypeScript/Vite, Ruff F dos Python alterados, sintaxe Bash e integridade do diff | Aprovados |

Os resultados finais, hashes e limites estão em [validacao_v48/correcao-faturamento-estoque-resumo.json](validacao_v48/correcao-faturamento-estoque-resumo.json).

Capturas da interface com dados sintéticos: [edição de receita existente](validacao_v48/correcao-financeiro-edicao.png) e [cadastro do recebimento em Compras](validacao_v48/correcao-compras-cadastro.png). A primeira vem dos cenários de interface com API controlada; a segunda, do fluxo completo com API e PostgreSQL reais.

A validação utiliza dados sintéticos e bancos descartáveis, com testes da API, migrações, navegador real, cálculo financeiro, concorrência, idempotência e recuperação de resposta perdida. O teste de migração compara todas as colunas anteriores das tabelas antes e depois da atualização, incluindo OS, orçamento e receita preenchidos.

Os cenários de Docker/HTTP do atualizador são controlados; PostgreSQL é executado de fato. A VPS Hostinger e a execução operacional de PowerShell não foram acessadas nesta validação. A publicação no GitHub e a aplicação da revisão no servidor são etapas distintas.
