# SÊNTICO V48 — correções de gravação e validação

**Data:** 25/11/2026. **Base recebida:** SENTICO_V47_CABECALHOS_FIXOS_TABELAS_20261123.zip.

## Organização no GitHub

O repositório mantém `apps/` e os arquivos Compose na raiz. Os caminhos de instalação e teste foram adaptados do ZIP, que usa `codigo-fonte/`. As correções de aplicação permanecem idênticas. Em 26/11/2026, o atualizador da VPS foi adaptado para V47 → V48, preservando o Compose de produção, os volumes e a revisão do banco. O procedimento exige execução no servidor e está descrito em [infra/vps/LEIA-ME-DEPLOY.md](infra/vps/LEIA-ME-DEPLOY.md); o procedimento V47 anterior foi arquivado em `infra/vps/historico/`.

## Resultado

A V48 corrige causas reproduzíveis de falha de gravação, respostas de erro depois de operações bem-sucedidas, perda de campos em atualizações parciais e conflitos entre operações simultâneas. As correções foram aplicadas ao projeto completo; esta entrega não executa uma atualização remota no computador ou servidor operacional.

Na validação final conjunta, **665 testes Python passaram, sem falhas nem erros; sete foram ignorados por dependerem de arquivos privados de uma conciliação histórica que não vieram no ZIP**. Essa execução inclui os testes da API, integrações com PostgreSQL real e verificações do instalador. A compilação TypeScript/Vite também passou. Os resultados não significam uma garantia de inexistência de qualquer defeito futuro: descrevem precisamente os cenários executados e as limitações abaixo.

## 1. Compras e solicitações de materiais

### Dados de estoque desapareciam da resposta

A função que montava a resposta da compra preenchia os campos `inventory_*`, mas o modelo público `PurchaseOutput` não os declarava. A validação da resposta removia esses campos. Ao reabrir o formulário, a tela recebia uma compra sem o destino de estoque salvo; uma edição seguinte podia apagar a configuração ou gerar conflito em compra já recebida.

O contrato agora devolve os campos de destino, identificação, nome, categoria, formato, modalidade e série. Atualizações de clientes anteriores que omitirem esses campos mantêm os valores persistidos. Foram testados criação, leitura, edição de observações, recebimento e reedição.

### Atualizar status apagava outras informações

O PATCH de uma solicitação atribuía valores padrão aos campos que não foram enviados. Agora modifica somente os campos presentes no envio. Fornecedor, referência da compra, rastreamento, previsão e custo sobrevivem a uma alteração isolada de status. Uma tentativa explícita de apagar o custo histórico de material já movimentado é recusada.

### Numeração e recebimentos simultâneos

A seleção do último número seguida de incremento podia gerar o mesmo código para duas operações concorrentes. A numeração anual de PC e SC agora usa bloqueio transacional no PostgreSQL, por tipo e ano, e considera o maior sufixo numérico válido. Códigos históricos fora do padrão não interrompem a sequência.

O recebimento concilia compra, solicitação e movimento físico dentro de uma transação protegida. Uma solicitação não pode tomar o vínculo do recebimento de outra. O saldo é relido depois de obter o bloqueio, evitando usar uma cópia antiga já carregada na sessão.

As verificações reais incluíram 16 criações paralelas de PC/SC, oito tentativas concorrentes de receber a mesma compra, recebimento simultâneo de PC e SC vinculadas nas duas ordens de envio, duas compras entrando no mesmo item e conflito de número de série. Foram conferidos códigos, quantidade persistida, número de movimentos e reversão integral da tentativa recusada.

### Compras históricas e custo da OS

Registros antigos recebidos antes da integração com estoque podem ter observações editadas sem exigir um novo recebimento. Essa edição não fabrica movimento nem data histórica. Um recebimento novo continua exigindo destino válido.

O custo de peças da OS agora é recalculado depois de descarregar as alterações pendentes para o banco. Isso corrige a agregação que consultava valores anteriores quando `autoflush=False`.

### Compra gravada com anexo pendente

A interface guarda imediatamente a identificação retornada pelo POST da compra. Se o envio do anexo falhar, apresenta a situação correta e mantém a mesma compra para a tentativa seguinte. O teste de navegador confirmou um POST, uma atualização da compra e duas tentativas de anexo, sem criar uma segunda compra.

## 2. Ordens de serviço

### Edição parcial e versão do registro

O formulário passa a enviar somente os campos alterados, acompanhados da versão lida. O backend bloqueia a linha, recarrega seu estado atual e verifica a versão antes de gravar. A edição, o status, os substatus e a inativação seguem a mesma proteção.

Se outra operação alterou apenas campos diferentes, a interface pode reaplicar uma única vez os campos locais sobre a versão atual. Se houve mudança no mesmo campo, preserva o que foi digitado e mostra o conflito, com uma ação explícita para recarregar. Atualizações após orçamento ou estoque não avançam a referência original do formulário por cima de uma edição conflitante.

Dois PATCH concorrentes com a mesma versão foram testados no PostgreSQL: uma resposta 200 e uma resposta 409, com apenas uma versão nova persistida. Também foram testados status contra edição e faturamento concorrente de uma OS.

### Equipamento sem série e campos que não podiam ser apagados

Salvar uma OS sem série não cria outro equipamento a cada gravação. Campos opcionais podem ser limpos sem o backend restaurar o valor antigo. Uma alteração real da série preserva a identidade de equipamentos que estejam vinculados a outras ordens históricas. Alterar um campo técnico não reaplica cópias antigas dos demais campos compartilhados.

Uma OS que já esteja vinculada a um cliente posteriormente inativado pode receber alterações em outros campos; o sistema continua validando a escolha de um novo cliente.

### Valores e limites dos campos

Entradas monetárias como `1.250,50` e `1250.50` são normalizadas. O sistema rejeita formatos inválidos, valores não finitos, negativos, precisão excessiva e valores superiores à capacidade da coluna. Zero permanece zero. Campos técnicos agora validam os limites reais do banco antes da gravação.

### Respostas lentas e mensagens falsas de erro

Uma consulta de histórico que falhar depois de uma gravação confirmada não transforma a gravação em falha. Consultas de fundo da listagem não bloqueiam a edição da OS. A sugestão de localização aplica somente a localização ao formulário atual e verifica a identidade da OS; uma resposta tardia não apaga texto digitado enquanto a consulta estava pendente.

## 3. Orçamentos, Comercial e Mecânica

Os rascunhos são salvos antes de deixar a aba ou fechar o detalhe. Se a consulta inicial dos orçamentos falhar, a tela não presume que não existe rascunho. Se a consulta de conferência falhar depois do salvamento, a identificação do rascunho confirmado é mantida para atualizar a mesma revisão na próxima tentativa.

Gravação, emissão e revisão dos orçamentos do laboratório são serializadas pela OS. Uma emissão simultânea com edição não permite alterar uma revisão já emitida. Solicitações simultâneas de revisão reutilizam o mesmo rascunho.

No Comercial, revisar novamente uma versão antiga passa a considerar a maior revisão da família. A sequência não tenta reutilizar um número já existente. A emissão e a edição também usam bloqueios.

A primeira geração simultânea de etiquetas mantém um único token de rastreamento, preservando os QR codes já entregues. Operações de envio, conferência, evidência fotográfica e encerramento do retorno de pintura verificam o controle bloqueado. Foi testada a disputa entre encerrar o retorno e desmarcar a conferência de uma peça.

## 4. Correções compartilhadas e demais módulos

| Área | Correção ou verificação principal |
|---|---|
| Persistência assíncrona | Valores de atualização gerados pelo banco são carregados durante o `flush`, evitando leitura implícita assíncrona ao montar a resposta (`MissingGreenlet`). |
| Notificações | Títulos e descrições de equipamento que excedem a coluna recebem prévia limitada; o texto completo fica nos detalhes. Uma notificação não cancela mais uma operação válida por excesso no tamanho da prévia. |
| Financeiro | Gravações que sincronizam faturamento com uma OS bloqueiam essa OS; receitas simultâneas legítimas produzem uma única transição para Faturado. A chave de idempotência é permitida no CORS. |
| Colaboradores | Histórico é recarregado após desligamento; desligamento duplicado é recusado; data anterior à admissão é validada; motivo longo permanece integral no histórico. |
| Clientes | Formulários pertencem ao cliente aberto, preservam o resultado confirmado e evitam envios concorrentes. O perfil `gestao` agora acessa o Cadastro Mestre conforme a permissão que já existia na API. Contatos, faturamento, notas e documentos foram exercitados por HTTP real. |
| Estoque | Resposta distingue movimento confirmado de falha na consulta posterior; saldo e custo foram conferidos após saída e devolução. Upload e remoção de foto também foram testados. |
| Comunicação | Repetição automática limitada a leituras GET/HEAD; gravações com resultado incerto não são reenviadas indiscriminadamente. Há timeout, cancelamento e identificação de resposta incompleta ou HTML inesperado. |
| Sessão | Uma falha temporária na consulta da sessão oferece reconexão, sem presumir automaticamente que o login expirou. |
| Diagnóstico | Erros de banco recebem JSON legível e referência de requisição. SQL, parâmetros e credenciais não são devolvidos ao navegador. |

A configuração de carregamento assíncrono foi conferida com a documentação oficial do SQLAlchemy: [AsyncSession e prevenção de I/O implícito](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession) e [carregamento de valores gerados pelo banco](https://docs.sqlalchemy.org/en/20/orm/persistence_techniques.html#fetching-server-generated-defaults).

## 5. Matriz de validação

| Grupo | Resultado final |
|---|---:|
| Testes da API: unidades, regressões, armazenamento, PDFs e integrações reais | 602 aprovados; 7 históricos ignorados |
| Instalador, volumes, compatibilidade, interface e isolamento da suíte | 63 aprovados |
| Total Python conjunto | **665 aprovados; 0 falhas; 0 erros; 7 ignorados** |
| Comportamento JavaScript de transporte, moeda e edição | 18 aprovados |
| Verificações anteriores do orçamento | 20 aprovadas |
| Preferências e temas V26/V27/V29 | 41 verificações aprovadas |
| Navegador Chromium com falhas de API controladas | 18 cenários aprovados; 0 erros JavaScript não tratados |
| Navegador Chromium com API e PostgreSQL reais, sem simulação de API | 12 verificações aprovadas; 0 erros JavaScript e 0 respostas HTTP de erro |
| TypeScript e compilação da interface Vite | Aprovados |
| Migrações em PostgreSQL 17.12 descartável | 50 migrações percorridas até `20261123_02` |

Os 18 cenários de navegador controlados incluem nove verificações de gravação, conflitos, anexo e resposta atrasada, além da abertura dos nove módulos: Painel, Compras, Laboratório, Estoque, Comercial, Financeiro, Clientes, Colaboradores e Notificações. As respostas controladas permitem reproduzir falhas de rede de forma determinística. A persistência real também foi validada pelos testes HTTP/PostgreSQL, sem mocks do banco ou da autenticação.

Na homologação adicional pelo navegador, com a API e o PostgreSQL reais, foram aprovadas a criação de compra, a edição e reabertura da compra, a edição e reabertura da OS e a navegação nos nove módulos. O valor digitado `1.234,56` foi confirmado no banco como `1234.56`. O PATCH da OS enviou somente modelo, observações e versão; após recarregar, a versão era 2 e os demais dados permaneciam preservados. A conta usada tinha perfil `gestao` e lista de módulos vazia, cobrindo o acesso administrativo que estava bloqueado incorretamente na tela de Clientes. O registro preserva três leituras canceladas pelo navegador durante trocas de tela, sem falha de gravação, erro JavaScript ou resposta HTTP de erro.

Os testes reais abrangem também login, logout, permissão LAB contra Financeiro, cadastro/edição de patrimônio, etiquetas PDF, relatórios financeiro PDF/XLSX, parcelas com centavos exatos, baixa e estorno, bloqueio de competência fechada, anexos, contatos, notas e ciclo de vida de colaboradores.

### Evidências

Os arquivos em `validacao_v48/` contêm o resultado JUnit, os resultados de navegador, logs de compilação e de verificações JavaScript e um resumo legível. A suíte de código permanece no pacote. Capturas de tela e binários de navegador usados na revisão não são incluídos.

O ambiente de execução utilizado para os testes Python foi Linux com Python 3.12.14 e PostgreSQL 17.12. O build e as verificações JavaScript foram executados com Node 24.22.3. As imagens Docker declaradas mantêm Python 3.13, Node 22 para compilação, PostgreSQL 17 e Caddy 2.10. As versões Python resolvidas foram fixadas em `requirements-v48.lock` e usadas na validação.

### Limitações objetivas

1. Os sete testes ignorados dependem dos CSVs privados `finance_reconcile_data`, ausentes no material recebido. Não foram inventados registros financeiros para fazê-los passar. Esses testes auditam uma importação histórica específica; não substituem os testes funcionais de Financeiro que foram executados.
2. O Docker Desktop/PowerShell do computador operacional e o banco real não foram acessados nesta revisão. A construção final das imagens e a instalação nesse ambiente precisam ser executadas pelo inicializador entregue. A execução equivalente de migrações e testes foi feita em PostgreSQL real, sem Docker.
3. Entrega real de Web Push e serviços externos que exigem credenciais não configuradas não foram exercitados. Não houve envio de mensagens ou notificações externas.
4. Os testes não reproduzem toda combinação possível de dados históricos, queda de energia, falta de disco, conexão física ou carga de produção. O diagnóstico incluído ajuda a distinguir essas condições de erros da aplicação.

## 6. Instalação e operação

Consulte `LEIA_PRIMEIRO_SENTICO.md` para o procedimento curto. O inicializador continua sendo `INICIAR_SENTICO.cmd`; os nomes do projeto e dos volumes de dados foram preservados. Não há nova migração de estrutura nesta V48. Instalações anteriores à revisão atual ainda aplicam as migrações que já pertenciam ao pacote V47.

O Compose operacional agora entrega a interface compilada por Caddy, sem Vite/HMR em execução. A API operacional usa dois processos sem `--reload`. O volume antigo de `node_modules` permanece preservado, mas deixa de determinar quais dependências a interface usa. O Compose de desenvolvimento continua separado.

A verificação de saúde operacional consulta a disponibilidade do banco. Depois de instalar, `http://127.0.0.1:5184/api/health/version` deve informar `version: "48"`. `DIAGNOSTICAR_SENTICO.cmd` verifica versão, disponibilidade da API/banco, reinícios e ocorrências de encerramento por memória, além dos dados de diagnóstico que já existiam.

## 7. Como repetir a validação

Execute `TESTAR_SENTICO.cmd` com Docker Desktop aberto. O script usa exclusivamente o projeto `sentico-v48-testes`, um PostgreSQL descartável em `tmpfs`, sem publicar portas e sem montar os volumes operacionais. Ele cria apenas usuários e dados sintéticos de teste. O relatório XML fica em `resultados_testes/api-e-instalador.xml`.

O atalho executa as migrações, a suíte Python, as verificações do instalador, os testes JavaScript e o build. O banco temporário é encerrado ao final. Os testes adicionais de navegador estão em `apps/web/tests/browser-reliability.py` e exigem Playwright e Chromium, conforme as instruções do próprio arquivo; eles não são instalados automaticamente pelo inicializador operacional.

Ao receber uma mensagem de gravação com resultado incerto por perda de comunicação, consulte o registro antes de enviar novamente. O sistema mantém os campos visíveis, mas uma conexão perdida depois do commit pode impedir a confirmação no navegador. Essa distinção evita tratar uma ausência de confirmação como certeza de que nada foi gravado.
