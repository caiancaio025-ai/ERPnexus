# V48 — faturamento de várias OS e orçamento conjunto

> **Histórico da primeira implementação.** O fluxo foi corrigido: as OS agora são adicionadas no próprio formulário financeiro, inclusive na edição de uma receita, e as caixas da lista do Laboratório foram retiradas. Consulte [a correção vigente e seu passo a passo](CORRECAO_V48_FATURAMENTO_ESTOQUE.md).

Atualização de **26/11/2026**, sobre a V48 com aparência compacta e recebimento individual. A aplicação continua identificada como versão **48**; o commit e a revisão de banco **`20261126_02`** identificam esta atualização.

## Faturar várias ordens de serviço

No **Laboratório → Ordens de serviço**, marque as caixas das OS desejadas e clique em **Faturar selecionadas**. O Financeiro abre com essa seleção. Também é possível adicionar várias OS diretamente em **Financeiro → Nova receita**, pela busca de ordens de serviço.

Confira os valores por OS, os documentos fiscais, o banco e o vencimento. Em **Parcelado**, informe os vencimentos e valores das parcelas; os atalhos de divisão e datas mensais continuam disponíveis. O botão **Faturar N OS** confirma o conjunto.

- As OS precisam pertencer à mesma empresa emitente e ao mesmo cadastro de cliente. Equipamentos iguais continuam diferenciados pela OS e pela série.
- Cada OS mantém seu valor e seus recebíveis. O sistema distribui as parcelas sem perder ou acrescentar centavos aos totais das OS ou dos vencimentos.
- Quando existe valor aprovado, o lote respeita o saldo ainda não lançado. Quando não existe, o usuário deve informar um valor positivo.
- As exigências de faturamento do cliente, como pedido de compra e envio de documentos, são conferidas para cada OS.
- Todas as OS são gravadas na mesma transação. Uma recusa não deixa parte do lote faturada. A repetição do mesmo envio confirmado não cria novas receitas.
- A tela de conclusão permite consultar as receitas de cada OS. Baixas, anexos e alterações posteriores continuam nos lançamentos correspondentes.

O limite é **50 OS por lote** e até **60 parcelas na tela**, respeitando no máximo **1.000 lançamentos resultantes**. Cada parcela de cada OS precisa ter pelo menos R$ 0,01; uma divisão impossível é recusada com orientação para ajustar os valores ou a quantidade de parcelas.

## NF de saída no Laboratório

A aba **Valores** da OS apresenta **NF de saída**, **NF de saída 2** e **NF de saída 3**. É possível preencher e corrigir esses campos, salvar e reabrir a OS.

Ao faturar, o campo **NF de saída nas OS** é sincronizado com cada OS selecionada. Uma única NF-e ou NFS-e preenche esse campo automaticamente. Quando os dois documentos têm números diferentes, escolha qual número deve constar na OS.

Uma nota que já esteja registrada é reutilizada. Uma nota diferente ocupa a próxima saída livre, preservando as anteriores. Se as três saídas estiverem ocupadas por outros números, o faturamento solicita a revisão da OS antes de gravar. O preenchimento manual na ficha atualiza os documentos da OS; os valores financeiros são alterados no Financeiro.

## Um orçamento para vários equipamentos

1. No **Laboratório**, selecione de duas a 50 OS do mesmo cliente e da mesma empresa emitente.
2. Clique em **Criar orçamento conjunto**. O sistema cria diretamente um rascunho com um item inicial para cada OS.
3. Preencha os serviços e valores de cada equipamento, o diagnóstico, o desconto e as condições comerciais comuns.
4. Use **Salvar rascunho** para continuar depois ou **Visualizar PDF** para conferir o documento.
5. Clique em **Salvar e emitir PDF** para emitir um único orçamento com todas as OS selecionadas.

O documento possui uma identificação própria, como **OC-000001**, e mostra cada OS, equipamento, número de série, itens, subtotal, desconto e total. Ao final, apresenta o total conjunto e as condições comerciais. O valor calculado de cada linha, inclusive quando a quantidade é fracionada, é arredondado para centavos antes da soma, com o mesmo cálculo na tela, na API e no PDF.

O orçamento pode ocupar mais de uma página, conforme a quantidade de equipamentos e de texto. Ele continua sendo um único documento, com código, revisão e paginação.

Veja o [exemplo de orçamento com quatro OS](validacao_v48/multiplas-os-exemplo-4-os.pdf), gerado com dados fictícios: quatro inversores do mesmo modelo, cada um com sua série e seu valor, em um PDF de duas páginas.

### Histórico e preservação

A seção **Orçamentos conjuntos** permite pesquisar código, cliente, título, OS ou série. O mesmo histórico também aparece na aba **Orçamento** de qualquer OS vinculada.

Uma revisão emitida preserva o PDF original e os dados usados na emissão. Alterações posteriores no cliente, na empresa ou no equipamento não modificam esse documento. Para mudar a proposta, use **Nova revisão**; o sistema reaproveita um rascunho já existente da família.

A emissão atualiza o valor orçado de cada OS com a sua participação no conjunto e registra o orçamento enviado. Mantém os valores aprovados, as receitas e o status principal de cada OS. Os orçamentos individuais continuam disponíveis.

Edição e exclusão de rascunho verificam a versão do documento. Uma alteração concorrente não é sobrescrita silenciosamente. Quando uma gravação perde sua resposta, a interface consulta o conteúdo persistido antes de considerar a operação inconclusiva.

## Banco, instalação e atualização

A migração **`20261126_01` → `20261126_02`** cria quatro tabelas próprias para conjuntos, revisões, vínculos de OS e itens. Ela não altera as tabelas anteriores nem converte orçamentos individuais em conjuntos. O PDF emitido, seus dados e seu hash ficam associados à revisão.

O instalador Windows, a descoberta de bancos e o atualizador da VPS reconhecem a nova revisão. Uma instalação de avaliação local já preparada na revisão anterior recebe somente a migração incremental, mantendo usuário, senha e dados.

No terminal da Hostinger, como root:

```bash
cd /opt/sentico-green &&
git pull --ff-only origin main &&
bash infra/vps/atualizar.sh
```

O atualizador aceita `20261123_02`, `20261126_01` e `20261126_02`. Faz backup, ensaia a atualização numa cópia restaurada, confere o estoque e as restrições do esquema e só então aplica a revisão e troca API/interface. Ao terminar, aguarde **`SENTICO_V48_ATUALIZADO=OK`** e use **Ctrl+F5**. O procedimento completo está em [infra/vps/LEIA-ME-DEPLOY.md](infra/vps/LEIA-ME-DEPLOY.md).

## Validação

Os resultados consolidados desta alteração estão em [validacao_v48/multiplas-os-resumo.json](validacao_v48/multiplas-os-resumo.json). As evidências anteriores continuam com seus nomes originais.

| Verificação final | Resultado |
| --- | --- |
| API e instalador | 747 aprovados; 7 não executados por dependerem de manifestos privados da conciliação histórica |
| Atualizador VPS, PostgreSQL e cenários controlados de implantação | 117 aprovados |
| Preparação e atualização incremental do ambiente local | 17 aprovados |
| Testes Node da interface | 28 aprovados |
| Verificações V41 de moeda e salvamento | 20 aprovadas |
| Navegador com API e PostgreSQL reais | 10 cenários aprovados; nenhum erro de página ou de servidor |
| Navegador com API controlada e React StrictMode | 8 grupos de cenários aprovados |
| Compilação de produção TypeScript/Vite | Aprovada |

A migração foi executada sobre um banco com OS, orçamento individual e receita já preenchidos. Os hashes e as contagens das tabelas anteriores permaneceram iguais. As quatro tabelas novas foram criadas vazias, e a repetição da migração não alterou os dados.

Os testes desta atualização usam bancos descartáveis e dados sintéticos. Incluem a API, o navegador com API/PostgreSQL reais, o cálculo de centavos, os conflitos de gravação, as tentativas simultâneas, o PDF imutável e a migração com registros anteriores. O código de navegador correspondente está em `apps/web/tests/grouped-quotes-billing-browser.py`.

**A VPS Hostinger e a execução operacional de Docker/PowerShell não foram acessadas nesta validação.** A disponibilidade no servidor depende de aplicar o comando acima na instalação existente.
