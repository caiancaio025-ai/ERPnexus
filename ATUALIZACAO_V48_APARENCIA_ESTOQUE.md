# V48 — aparência no cabeçalho e recebimento individual

Atualização de **26/11/2026**, sobre a V48 já publicada no ERPnexus. A identificação da aplicação continua sendo versão **48**. O commit mostrado pelo atualizador identifica a revisão aplicada.

**Ambiente de avaliação local incluído:** para experimentar esta atualização em um banco separado, execute `INICIAR_TESTE_V48.cmd` e siga [COMECE_AQUI_TESTE_V48.txt](COMECE_AQUI_TESTE_V48.txt).

## Aparência

Nos nove módulos, o cabeçalho passa a apresentar **Aparência → nome do usuário → Sair**, depois das ações específicas da tela. O bloco volumoso de aparência e perfil foi retirado do rodapé lateral.

O botão abre as opções Claro/Escuro, Temas comemorativos e Animar decoração. As preferências salvas foram mantidas. O painel aceita teclado, coloca o foco no tema selecionado, fecha com Escape, clique fora ou botão Fechar, e funciona em telas pequenas.

[Captura do novo cabeçalho](validacao_v48/atualizacao-aparencia-desktop.png), com dados sintéticos de teste.

## Recebimento de compras e solicitações

A quantidade é a mesma informada na compra/solicitação. O destino do recebimento apresenta uma prévia, sem pedir que o usuário digite a quantidade novamente.

| Controle escolhido | Exemplo com quantidade 10 | Identificação |
|---|---|---|
| Por quantidade | Um cadastro com saldo 10 | Uma etiqueta EST para o cadastro |
| Individual | Dez cadastros, cada um com saldo 1 | Dez códigos e etiquetas EST diferentes |

O código EST é interno e gerado automaticamente. A série do fabricante é um dado separado e opcional: não é inventada pelo sistema nem necessária para receber uma unidade. Para uma compra com uma unidade, ela pode ser informada no recebimento; para várias, pode ser preenchida depois em cada item do Estoque. Uma série informada continua tendo unicidade por empresa.

O controle individual aceita **até 1.000 unidades por recebimento**. Uma quantidade maior é recusada integralmente; o usuário pode escolher controle por quantidade ou dividir a compra em solicitações menores. O sistema não reduz a quantidade silenciosamente. O limite anterior de 100.000 unidades da compra por quantidade permanece.

### Gravação, repetição e vínculos

- Salvar os dados do destino sem mudar o status preserva a escolha ao reabrir a solicitação.
- Receber a mesma compra/solicitação novamente não gera unidades adicionais.
- Uma PC e uma SC vinculadas compartilham o grupo completo de entradas. Recebimentos simultâneos são conciliados dentro da transação.
- A quantidade histórica recebida é usada nessa conciliação, mesmo quando uma unidade já foi consumida ou devolvida.
- Quantidades, custos e destino de uma entrada já confirmada continuam protegidos. A referência de pedido de uma SC fisicamente vinculada não pode apontar para outro pedido.
- A edição da série opcional em Estoque mantém o código EST e o saldo. Omitir esse campo em um cliente anterior preserva a série existente.

## Banco e implantação

A migração incremental **`20261126_01`**, a partir de `20261123_02`, acrescenta um índice de unidade ao movimento. Cada entrada histórica recebe índice 1; saldos, custos, códigos e vínculos anteriores são mantidos. A unicidade passa a ser por origem e índice, permitindo várias unidades da mesma compra sem duplicar a unidade. O downgrade dessa migração é bloqueado.

O atualizador da VPS foi adaptado para reconhecer tanto a revisão anterior quanto a nova. Ele faz backup, restaura o backup em PostgreSQL descartável, compara hashes e totais de estoque antes/depois da migração na cópia e só então aplica a migração prevista no banco existente. A troca da aplicação continua limitada à API e à interface. Uma recuperação das imagens não restaura dados por cima do banco nem faz downgrade.

Para aplicar esta atualização, no terminal da Hostinger, como root:

```bash
cd /opt/sentico-green &&
git pull --ff-only origin main &&
bash infra/vps/atualizar.sh
```

Aguarde **`SENTICO_V48_ATUALIZADO=OK`** e pressione **Ctrl+F5** no navegador. A compilação ocorre antes da manutenção; backup, ensaio e troca exigem um período de manutenção. Consulte [o guia de implantação](infra/vps/LEIA-ME-DEPLOY.md) para resultados e recuperação.

O instalador Windows também reconhece a nova revisão, inclusive ao repetir a instalação em um banco já atualizado.

## Validação

| Verificação | Resultado |
|---|---|
| API completa + instalador, com PostgreSQL 17.12 descartável | **684 aprovados; sete históricos ignorados; zero falhas** |
| Build TypeScript/Vite | Aprovado |
| Testes JavaScript | 18 testes e 20 verificações do salvamento aprovados |
| Navegador com API e PostgreSQL reais | **17 cenários aprovados; zero erros de página/HTTP** |
| Verificação visual complementar com respostas controladas | Sete grupos aprovados; desktop e mobile de 390/320 px |
| Fluxo Bash/Git de implantação, com Docker/HTTP simulados | 23 cenários aprovados; oito de recuperação/repetição novamente aprovados após o ajuste final |
| Helpers do atualizador com PostgreSQL 17 real | 90 testes aprovados |
| Backup, restauração e migração de dados históricos em PostgreSQL 16.2 com clientes correspondentes | Cinco casos aprovados; hashes e totais preservados |
| Inicializador do teste manual e instalador existente | 69 verificações aprovadas: cinco contratos de isolamento e 64 testes do instalador |
| Preparação do banco de avaliação | 12 testes aprovados, incluindo criação, login e repetição em PostgreSQL 17.12 real |

O navegador real verificou os nove cabeçalhos, persistência de temas, teclado/fechamento, layout mobile, SC de dez unidades, gravação/reabertura, recebimento repetido, série opcional preenchida depois, PC individual com uma/três unidades, PC por quantidade e encerramento da sessão pelo cabeçalho.

Os testes de backend incluem recebimento simultâneo de PC/SC, dez unidades sem série, limite aceito de 1.000, conflito de série, custos de consumo/devolução, reversão integral de uma tentativa recusada e migração com dados históricos. Os sete testes ignorados dependem de arquivos privados de conciliação ausentes; não são cenários desta alteração.

O [resumo consolidado](validacao_v48/atualizacao-resumo.json) registra os resultados e hashes dos arquivos principais. As evidências desta atualização usam o prefixo `atualizacao-` em [validacao_v48](validacao_v48/). Os resultados anteriores foram preservados como histórico da entrega inicial.

O [resumo do teste local](validacao_v48/teste-local-resumo.json) registra a validação adicional do novo inicializador. O teste PostgreSQL confirmou login com Gestão, cookie separado, Financeiro e as três empresas; uma nova execução preservou senha alterada, nome, catálogo e fornecedor fictício. Os testes automatizados registrados não incluem a execução do PowerShell e do Docker Desktop no Windows. As contagens acima têm escopos sobrepostos e não devem ser somadas.

**Nenhuma implantação na VPS ou execução Docker operacional foi realizada nesta validação.** O fluxo Bash usa simuladores estritos de Docker/HTTP; API, PostgreSQL e navegador foram exercitados de verdade em ambientes descartáveis. A situação real da Hostinger será conferida pelo atualizador quando o comando acima for executado.
