# SÊNTICO V48 — estabilidade de gravação

**V48, com atualização de aparência e recebimento em 26/11/2026.**

Aparência agora fica no cabeçalho, ao lado do usuário. Compras individuais utilizam a quantidade informada, recebem códigos EST automáticos e não exigem série do fabricante. Consulte [o relatório desta atualização](ATUALIZACAO_V48_APARENCIA_ESTOQUE.md).

Neste repositório e no pacote atual, `apps/` e os arquivos Compose ficam diretamente na raiz. Os caminhos do instalador e dos testes foram adaptados a essa organização. O ZIP inicial entregue em 25/11 usava a pasta intermediária `codigo-fonte/`. Esta versão inclui a atualização de aparência e recebimento e o ambiente separado para avaliação local.

Esta versão corrige falhas de gravação em Compras e nas ordens de serviço, conflitos entre usuários, duplicação na tentativa de reenviar anexos, perda de campos e mensagens de erro após uma operação já confirmada. Também inclui correções em Estoque, Orçamentos, Comercial, Clientes, Colaboradores e Financeiro.

A validação conjunta da entrega inicial terminou com **665 testes Python aprovados, nenhuma falha e sete testes históricos ignorados por falta dos CSVs originais**. A compilação da interface, os testes JavaScript, 18 cenários de navegador com falhas controladas e 12 verificações com navegador/API/PostgreSQL reais passaram. Os detalhes, a cobertura e as limitações estão em `RELATORIO_V48_ESTABILIDADE_E_TESTES.md`.

## Experimentar a atualização primeiro

Extraia o ZIP em uma pasta própria, abra o Docker Desktop com containers Linux e execute **`INICIAR_TESTE_V48.cmd`**. Acesse o endereço exibido, por padrão **http://127.0.0.1:5185/**, com o usuário e a senha de teste. O roteiro completo está em **`COMECE_AQUI_TESTE_V48.txt`**.

Esse teste manual usa o projeto **`sentico-v48-teste-local`**, com banco e uploads próprios. Ele começa com o usuário de avaliação e os cadastros mínimos do sistema. Use **`PARAR_TESTE_V48.cmd`** para parar os serviços; iniciar de novo mantém os registros de teste.

## Atualizar a instalação existente, após a validação

1. Faça um backup atualizado do PostgreSQL e dos uploads da instalação em uso. Mantenha também o pacote anterior para eventual retorno.
2. Extraia **todo o ZIP** em uma pasta no Windows. Execute os arquivos a partir da pasta extraída.
3. Abra o Docker Desktop com containers Linux.
4. Dê duplo clique em **`INICIAR_SENTICO.cmd`**. A primeira compilação pode levar alguns minutos.
5. Aguarde a mensagem **`SENTICO_INICIADO=OK`**.
6. Abra **http://127.0.0.1:5184/**. Na primeira abertura após atualizar, use **Ctrl+F5** para carregar a nova interface.
7. Confira **http://127.0.0.1:5184/api/health/version**: a resposta deve conter **`"version":"48"`**.
8. Abra uma compra e uma OS conhecidas, faça uma alteração identificável e reabra o registro para conferir os dados no seu ambiente.

As correções estão no pacote entregue. O computador, o Docker Desktop e o banco operacional precisam executar essa atualização para utilizá-las.

## Arquivos principais

| Arquivo | Finalidade |
|---|---|
| `INICIAR_TESTE_V48.cmd` | Abrir a versão para avaliação manual com banco separado. |
| `PARAR_TESTE_V48.cmd` | Parar a avaliação e preservar os dados de teste. |
| `COMECE_AQUI_TESTE_V48.txt` | Passos para iniciar, entrar e conferir as mudanças. |
| `INICIAR_SENTICO.cmd` | Instalar/atualizar e iniciar o sistema operacional. |
| `TESTAR_SENTICO.cmd` | Executar testes em banco descartável separado do sistema em uso. |
| `DIAGNOSTICAR_SENTICO.cmd` | Consultar versão, API/banco, reinícios, memória e volumes; somente leitura. |
| `RELATORIO_V48_ESTABILIDADE_E_TESTES.md` | Causas encontradas, correções, testes, cobertura e limitações. |
| `validacao_v48/` | Evidências da validação desta entrega. |
| `apps/` e arquivos da raiz | Projeto completo, incluindo testes e dependências fixadas. |

`INSTALAR_SENTICO.ps1` é chamado pelo inicializador e não precisa ser executado separadamente.

## Dados existentes

O projeto operacional continua sendo **`sentico-v14-recuperado`**. Os volumes de PostgreSQL e uploads são descobertos/reutilizados pelo instalador existente. O arquivo de configuração permanece em `%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao`.

A atualização de 26/11 aplica a migração incremental **`20261126_01`**, que mantém os dados anteriores e permite várias unidades individuais por recebimento. O pacote não contém contas de teste habilitadas para a instalação operacional. Os usuários sintéticos são criados somente pelo projeto separado de testes.

A interface agora é compilada e servida por Caddy. A API operacional não usa recarga automática de código. O antigo volume de dependências do frontend é preservado, mas a interface passa a usar os arquivos da imagem construída.

**Não utilize `docker compose down -v`, `docker volume rm` ou `docker volume prune` para aplicar a atualização.** Esses comandos não fazem parte do procedimento e podem apagar dados.

## Testar sem usar os dados operacionais

Execute **`TESTAR_SENTICO.cmd`**. Ele cria o projeto **`sentico-v48-testes`**, sem portas publicadas, com banco temporário e sem acesso aos volumes do sistema operacional. Faz migrações, testes da API e do instalador, verificações JavaScript e compilação da interface.

O relatório fica em **`resultados_testes/api-e-instalador.xml`**. Sete testes da conciliação histórica são ignorados enquanto os respectivos CSVs privados não estiverem disponíveis. Os testes de navegador, que exigem Playwright/Chromium, têm roteiro separado no código-fonte.

## Se ainda aparecer um erro

Preserve o texto digitado. Se a mensagem indicar que não foi possível confirmar uma gravação, consulte o registro antes de enviar novamente. Uma perda de conexão pode ocorrer depois de o banco ter confirmado a operação.

Execute `DIAGNOSTICAR_SENTICO.cmd` e anote o módulo, a ação, o horário e a **Referência** exibida na mensagem. Esses dados permitem relacionar a falha ao registro técnico da requisição. Não é necessário compartilhar senhas, arquivo `.env` ou o banco inteiro para informar o erro.

## Histórico

A documentação original da V47 foi preservada em `historico_documentacao/LEIA_PRIMEIRO_V47_ORIGINAL.md`. Os relatórios antigos descrevem suas respectivas versões; para esta entrega, utilize as instruções e o relatório V48.
