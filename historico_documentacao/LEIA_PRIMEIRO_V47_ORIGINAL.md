# SÊNTICO V47 — Instalação Windows (ponto único)

Esta versão parte da **V46** e acrescenta **cabeçalhos fixos nas tabelas** para acompanhar os registros sem perder a identificação das colunas. A alteração é exclusivamente visual e preserva todos os dados e correções anteriores, inclusive as fotos da Mecânica/Pintura. **Não exige migração nova**; quem ainda não aplicou a migração Alembic `20261123_02` da V46 deve mantê-la no processo de instalação. Leia `ATUALIZACAO_V47_CABECALHOS_FIXOS_TABELAS_20261123.md` e faça backup antes de atualizar.

## V47 — Títulos de tabelas congelados

- A faixa **O.S., Cliente, Equipamento/Série, Localização, NF, Garantia, Status etc.** permanece visível durante a rolagem dos registros no Laboratório.
- Outras tabelas semelhantes também ganharam cabeçalhos fixos: Compras, Comercial, Colaboradores, Clientes e relatório/grade do Financeiro.
- Suporta temas claro e escuro e rolagem horizontal onde houver muitas colunas.
- A listagem de O.S. no celular mantém o formato em cartões; a impressão continua sem altura limitada.
- Nenhum dado, status, perfil ou regra de negócio foi alterado.


## V36 — Chaves das notas fiscais organizadas

- Dentro de **Notas fiscais da OS**: NF de entrada, NF de saída, chave de entrada (44 dígitos) e chave de saída (44 dígitos).
- Dentro de **Garantia 1**, **Garantia 2** e **Garantia 3**: cada cartão tem NF de entrada, chave de entrada, NF de saída e chave de saída.
- O sistema valida o comprimento das chaves, permite deixar em branco e conserva notas existentes. A chave de cada garantia é independente das demais.
- As alterações aparecem tanto no **cadastro de nova O.S.** quanto em **Dados da O.S.**; o formulário salvo é persistido na API e no PostgreSQL.
- **Migração `20261123_01` necessária** (somente seis colunas opcionais); executada pelo instalador. Não aplique sem backup.
- Todos os demais módulos, dados, temas e o instalador foram preservados.

**Homologação:** 45 testes do instalador aprovados; migração em banco de ensaio validada e 61 arquivos TS/TSX sem erros sintáticos. O build completo do React/Vite e o teste integrado real no Docker/PostgreSQL ainda estão pendentes.


## V45 — Remoção de fotos do Estoque (23/11/2026)

- Abra **Estoque → item → Detalhes**: cada foto agora tem o botão **Remover foto**.
- A exclusão pede confirmação e afeta **somente a foto selecionada**, sem apagar o item, saldo, outras fotos ou movimentações.
- A ação usa um endpoint autorizado do Estoque. O banco é atualizado antes da exclusão do arquivo físico para evitar perder arquivos se houver falha ao gravar.
- Caso a exclusão falhe, a foto permanece no item e o erro aparece na própria janela.
- Se uma foto tiver sido escolhida no cadastro/edição mas ainda não enviada, use **Descartar foto selecionada** antes de salvar.
- Não exige migração de banco, não altera volumes nem o instalador.

Leia `ATUALIZACAO_V45_REMOCAO_FOTOS_ESTOQUE_20261123.md` antes de instalar.

## Execute apenas este arquivo

**`INICIAR_SENTICO.cmd`** na raiz do ZIP extraído.

1. Faça backup do PostgreSQL e dos uploads atuais antes de atualizar um ambiente com dados reais.
2. Extraia o ZIP inteiro em uma pasta no Windows; não execute diretamente de dentro do ZIP.
3. Abra o Docker Desktop com containers Linux.
4. Dê duplo clique em `INICIAR_SENTICO.cmd`.
5. Depois de `SENTICO_INICIADO=OK`, abra **http://127.0.0.1:5184/**.

O arquivo `INSTALAR_SENTICO.ps1` é a rotina interna chamada pelo único inicializador: **não precisa executá-lo separadamente**.
O utilitário `DIAGNOSTICAR_SENTICO.cmd` é **somente leitura**, não instala nem recria containers.

## O que foi simplificado

- Removidos os 3 atalhos antigos `INICIAR_SENTICO_GREEN.cmd`, `INICIAR_SENTICO_V14.cmd` e `INICIAR_SENTICO_V15.cmd`.
- Removido o atalho técnico `INSTALAR_SENTICO_DEV.ps1`.
- A rotina PowerShell antiga foi renomeada para `INSTALAR_SENTICO.ps1`, sem mudar o projeto/volumes Docker.
- Documentações de versões antigas estão em `historico_documentacao/`; não servem como instruções de instalação atuais.

## Proteção dos dados

O projeto Compose continua sendo **`sentico-v14-recuperado`**, de propósito: trocar esse nome poderia causar novos volumes e containers, fazendo parecer que os dados sumiram.
Os volumes padrão permanecem:

- `sentico-v14-recuperado_pgdata`
- `sentico-v14-recuperado_uploads`
- `sentico-v14-recuperado_node_modules`

O instalador ainda descobre volumes do projeto existente e reutiliza o arquivo de configuração em `%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao`. Ele não apaga bancos/volumes, não altera usuários ou senhas de login do ERP nem importa backups sobre volume ocupado.
**Não execute** `docker compose down -v`, `docker volume rm` ou `docker volume prune`.

## Catálogo PostgreSQL — diagnóstico corrigido

O catálogo identifica o SÊNTICO por 5 tabelas (users, laboratory_customers, laboratory_work_orders, purchase_orders, alembic_version) e uma revisão Alembic reconhecida, sem exigir que haja OS ou clientes cadastrados. Agora analisa também o banco padrão `postgres`, caso o ERP esteja nele.

Se nenhum banco corresponder ao esquema e à revisão esperados, **a instalação para com segurança** e informa `BANCO_DESCARTADO_...` no log. Não troca para um banco vazio nem cria outro usuário automaticamente.

**Não envie** `.env`, senhas, backups, bancos ou arquivos de clientes. Se necessário, compartilhe somente as linhas que começam com `CATALOGO:` e o código de erro final — elas não incluem credenciais nem dados de clientes.

## Atualização de interface — menu lateral unificado

- Painel, Financeiro, Laboratório, Clientes, Colaboradores, Estoque, Compras e Comercial compartilham a **mesma barra lateral** (posição, dimensões, cores, marca, usuário e botão de saída).
- **Estoque agora também tem menu lateral**, mantendo suas abas já existentes.
- O menu recolhe para mostrar apenas os ícones; o estado fica salvo e continua igual após navegar entre módulos.
- Em telas pequenas, o menu abre como painel móvel. Os atalhos internos de cada módulo continuam acessíveis.
- O instalador único, o projeto Docker e todos os procedimentos de proteção dos volumes foram mantidos.

## Validação desta atualização

A sintaxe dos arquivos TS/TSX e do CSS alterado foi verificada estaticamente. A compilação integral do frontend depende de obter as dependências NPM e não pôde ser executada neste ambiente. Antes de aplicar em produção, valide a instalação e a navegação no Docker Desktop do Windows, mantendo o backup dos dados.

## Atualização financeira — Receitas com acesso direto à O.S.

- Na tabela **Financeiro > Receitas**, o botão **Ver OS** aparece nos lançamentos de receita que possuem uma `work_order_id` vinculada. Ele abre a própria O.S. no Laboratório, na aba **Valores**, com valor orçado e valor aprovado.
- Nos detalhes desses lançamentos, os botões **Ver orçamento da OS** (aba Orçamento) e **Ver valor aprovado** (aba Valores) dão acesso direto às informações do equipamento.
- O vínculo é feito pelo identificador persistido da O.S., não pela descrição, nome do cliente ou série; lançamentos sem O.S. associada não mostram o botão para evitar direcionamento incorreto.
- Não foram alterados banco de dados, rotinas financeiras, permissões, volumes Docker ou instalador único.

**Verificações desta atualização:** análise da navegação existente e da API, verificação de sintaxe TSX via TypeScript e checagens estáticas dos vínculos e destinos. A compilação total e o teste integrado com Docker/Windows dependem do ambiente de execução e devem ser feitos antes de colocar em produção.

## Atualização — O.S. → Receitas e pagamentos parcelados (12/11/2026)

- Na **O.S. do Laboratório**, usuários autorizados a acessar os valores agora encontram **Ver receitas / parcelas** no cabeçalho. A aba **Valores** mostra também quanto foi lançado, recebido, ainda está em aberto e o que falta lançar em relação ao valor aprovado.
- O botão abre **Financeiro → Receitas** na O.S. exata por ID, sem depender do período pesquisado. A tela exibe **todos os títulos e parcelas** associados à O.S., inclusive vencimentos de outros meses e parcelas já recebidas.
- Cada parcela pode ser aberta isoladamente para consultar, baixar, desfazer a baixa (conforme as regras existentes) e anexar o respectivo comprovante. A navegação de volta para a O.S. foi preservada.
- Ao escolher **Cadastrar receita da OS**, o cadastro já vem com vínculo, empresa e cliente. Havendo valor aprovado ainda não lançado, a sugestão é **apenas a diferença**, para evitar dupla contabilização. Quando o total já foi lançado, esse botão fica indisponível; valores excedidos são sinalizados.
- No cadastro **Parcelado** surgiram ações opcionais para **dividir o valor total em parcelas com centavos exatos** e **sugerir vencimentos mensais**. Cada valor/data permanece editável antes de salvar. A API já persistia parcelas separadas, permitindo baixar cada vencimento individualmente e mantendo auditoria.
- Ao seguir da O.S. para Receitas, o sistema salva primeiro eventuais alterações não salvas da O.S.; se o salvamento falhar, permanece no Laboratório.

**Proteção dos dados:** nenhuma migração de banco, mudança de identificador, volume Docker, backup, script ou nome do projeto Compose foi introduzida. A rotina `INICIAR_SENTICO.cmd` e os procedimentos anteriores continuam os mesmos. Atualize com backup de banco e uploads.

**Validação:** sintaxe TS/TSX e Python validada; testes unitários de cálculo de saldo e parcelamento passaram. Não foi possível executar a compilação completa do frontend nem os testes integrados dependentes de PostgreSQL/Docker neste ambiente. Teste em uma cópia segura do ambiente Windows antes de produção.

## Correção — Exclusão DEFINITIVA de endereços (12/11/2026)

- Em **Estoque → Endereços → Excluir definitivamente**, o botão remove do banco o endereço e as posições físicas relacionadas, inclusive endereços que já estavam arquivados.
- Se o endereço ainda estiver atribuído a algum item (mesmo item sem saldo), a operação é bloqueada: mova o item para outro local ou selecione **Sem localização** primeiro. Sublocais também devem ser excluídos antes do endereço pai.
- Quando houver histórico de posições, **o endereço é apagado**, não arquivado. O sistema guarda somente o código anterior/novo nos eventos históricos (sem manter o endereço/posição ativa nem os vínculos de chave estrangeira). Movimentações de peças, OS e valores do estoque não são excluídos.
- O formulário pede confirmação porque a exclusão é irreversível. Endereços antes arquivados aparecem em **Mostrar arquivados** e podem agora ser apagados definitivamente por esse mesmo botão.
- Caso algum outro vínculo impeça a exclusão, a transação é revertida e o ERP exibe um erro; não há arquivamento automático nem aviso falso de exclusão.

**Migração de banco necessária:** `20261112_01`, encadeada a `20261028_01`. Ela acrescenta duas colunas de texto ao histórico de localização e preenche os códigos existentes antes de permitir a exclusão física. O instalador único foi atualizado para reconhecer **as duas revisões** e aplicar a migração ao banco existente, sem trocar o projeto ou apagar volumes. Faça backup do banco e dos uploads antes da instalação.

**Validação:** 83 testes automatizados pertinentes passaram, incluindo teste com chaves estrangeiras `RESTRICT` em banco SQLite de ensaio e testes do instalador. Alembic reportou a nova revisão como `head`. Não foi possível executar homologação completa Windows/Docker/PostgreSQL neste ambiente: teste primeiro em uma cópia com backup.


## V16 — Pesquisa de posição, mobile e notificações também no desktop (16/11/2026)

- No formulário **Estoque → Novo item**, o campo **Posição física** agora é pesquisável por estante, gaveta, caixa, nome, área ou código e preserva as localizações existentes.
- Foram acrescentados refinamentos CSS **somente para telas de celular (menos de 768 px)**: entradas com fonte adequada ao iOS, formulários mais legíveis, botões de toque e modais ajustados à altura da tela. A apresentação desktop foi mantida.
- O painel inclui um controle de notificações **neste computador / neste celular** no sino de alertas, disponível para aplicativos web instalados pelo Edge/Chrome e navegadores compatíveis. O serviço Web Push requer HTTPS, permissão do usuário e configuração de chaves VAPID no backend.
- O instalador reconhece a nova migração `20261116_01` a partir de `20261112_01`. Não troca volumes nem bancos. Não é necessário reinstalar o aplicativo no celular ou no desktop: abra-o após a atualização e ative os avisos.
- As mensagens do sistema operacional não revelam valores nem nomes de clientes. Ao sair do sistema, a assinatura do dispositivo é revogada.
- **Consulte `ATUALIZACAO_V16_ESTOQUE_MOBILE_PUSH.md` antes de implantar**, principalmente para configurar chaves e testar avisos no Windows e no telefone. Um executável WebView2 próprio tem limitações distintas da PWA; não há código desse executável neste pacote.

**Homologação:** testes estáticos e do instalador foram executados; sem promessa de validação completa do frontend e push real até a instalação local com banco, browsers e HTTPS. Faça backup e valide em ambiente separado primeiro.

## V17 — Correção dos orçamentos com fotos (17/11/2026)

- Corrigido conflito de unicidade ao salvar orçamentos que já possuem fotos: preços, legendas e laudos podem ser alterados no rascunho sem recriar vínculos das imagens.
- A revisão admite até **10 fotos**, sem duplicatas, com indicação do contador no formulário e mensagens claras de erro e de alterações pendentes.
- O PDF reúne legenda e fotografia na mesma página e só marca a revisão como emitida **após a geração bem-sucedida**.
- Sem alteração de banco, instalador, nome do projeto ou volumes. Continue a usar apenas **`INICIAR_SENTICO.cmd`**.
- Consulte **`ATUALIZACAO_V17_ORCAMENTOS_COM_FOTOS.md`** para testes, limitações e preservação de documentos emitidos.

## V18 — Central interna de notificações e fontes mobile (17/11/2026)

- O sino no painel mostra as movimentações recentes, com **Ampliar** para a central `/notificacoes` e novo item no menu lateral.
- A página completa traz pesquisa por OS, equipamento e responsável; filtros por setor, ação, pessoa, período e não lidas; histórico paginado e marcação de leitura.
- OS, análise técnica, orçamentos, solicitações de material, compras, recebimentos, estoque, financeiro e outras ações importantes geram eventos com o nome do responsável, contexto e data.
- **Gestão vê tudo; ADM, apenas orçamentos; técnicos não recebem eventos financeiros.** O controle existe também na API, não apenas na tela.
- Avisos Web Push e notificações externas do navegador foram desativados nesta versão; a atividade é exibida **dentro do SÊNTICO**. As instruções de Web Push da seção V16 acima são históricas e **não se aplicam à V18**.
- Fontes, filtros e metadados foram adaptados a celulares (CSS específico abaixo de 768px), mantendo o visual desktop.
- **Migração obrigatória:** Alembic `20261117_01` (a partir de `20261116_01`); instalador e scripts de inspeção reconhecem a nova revisão.
- Consulte `ATUALIZACAO_V18_CENTRAL_NOTIFICACOES_20261117.md` antes de atualizar. Faça backup, execute `INICIAR_SENTICO.cmd` e homologue localmente antes de subir à VPS.

**Validação V18:** 54 testes dirigidos de backend, 28 testes do instalador e ensaio SQLite de permissões/histórico aprovados. Sem build frontend completo nem homologação PostgreSQL/Docker/Windows neste ambiente.

## V19 — Português, Central de Notificações e temas (17/11/2026)

- Nova opção **Aparência → Claro / Escuro** no menu lateral de todos os módulos. A escolha é salva no navegador/dispositivo; tema escuro continua o padrão. O login e o menu lateral mantêm a identidade de marca escura.
- Central de Notificações com visual renovado, destaques discretos, pesquisa principal, resumo de atividades, filtros avançados recolhíveis e atalhos para não lidas e atividades do dia; mobile com campos e botões de tamanho confortável.
- Status conhecidos e algumas mensagens comuns de erro foram traduzidos. Exemplo: `OS OS-30740 · Warranty` passa a `OS 30740 · Garantia` **na interface**, inclusive para notificações antigas, sem reescrever dados existentes.
- Sem alterações de banco, API de permissões, volumes Docker ou instalador. Continuam valendo as proteções da V18 (Gestão vê todos os setores; ADM só orçamentos; técnicos sem financeiro). Pop-ups externos e Web Push seguem desativados.
- Consulte `ATUALIZACAO_V19_PORTUGUES_TEMAS_NOTIFICACOES_20261117.md` para arquivos, validação, limitações e testes locais.

**Validação V19:** 56 arquivos TS/TSX sem erros sintáticos; 28 testes do instalador e 16 testes de API selecionados aprovados. Build integral do frontend e inspeção visual em Docker/Windows pendentes; faça backup e homologue localmente antes de colocar na VPS.


## V20 — Cores dos status e Central de Notificações (17/11/2026)

- No **tema claro**, etiquetas como **Sem conserto** (vermelho), **Aprovado** (verde) e **Aguardando** (âmbar) recuperam suas cores semânticas, preservando os tons do tema escuro.
- O estado `in_analysis` passa a aparecer como **Analisado** nas telas, notificações e documentos técnicos; o código original, histórico e fluxo operacional não foram alterados.
- Notificações no painel e na central recebem diferenciação por módulo em cores discretas, com destaque para não lidas.
- Nenhuma migração nova, atualização de banco, troca de nome do Compose ou mudança de volumes.
- Consulte `ATUALIZACAO_V20_CORES_STATUS_NOTIFICACOES_20261117.md` para instruções e testes.

**Validação:** testes de regressão e sintaxe realizados; compilação completa de frontend e homologação Windows/Docker/PostgreSQL ainda requeridas antes de produção.


## V21 — Painel inicial de trabalho por função (17/11/2026)

- Gestão: visão consolidada de laboratório, orçamentos pendentes, compras e finanças.
- ADM: somente atividades de orçamentos; LAB: entradas e serviços aprovados; Compras: solicitações pendentes e entregas; Estoque: recebimento e separação de materiais.
- Cada quadro exibe contagem, até cinco itens e link para o registro ou módulo, conforme permissão. O painel atualiza periodicamente enquanto visível.
- Botões e status no módulo Colaboradores ganharam contraste legível no tema claro.
- Sem migração adicional de banco, modificação de volumes ou alteração da VPS. Execute apenas `INICIAR_SENTICO.cmd` para testar.
- Detalhes em `ATUALIZACAO_V21_PAINEL_POR_FUNCAO_20261117.md`.


## V23 — Laboratório mobile corrigido (17/11/2026)

- A listagem de **O.S. do Laboratório** no celular deixou de comprimir as colunas da tabela. Em telas pequenas, cada O.S. agora aparece em formato de **cartão legível**, com número da O.S., cliente, equipamento, status, prioridade, localização, notas fiscais, garantia e data sem ficar na vertical.
- O **status** volta a ficar visível no celular, inclusive com os substatus e a identificação de O.S. inativa quando houver.
- O **detalhe da O.S.** foi reorganizado para mobile: cabeçalho com melhor quebra de texto, ações sem sobreposição, abas maiores e mais confortáveis ao toque, além de rodapé com botões empilhados.
- A visualização desktop foi preservada. Não houve alteração de banco, APIs, permissões, volumes Docker, nome do projeto Compose ou regras de negócio.
- Consulte `ATUALIZACAO_V23_MOBILE_LABORATORIO_20261117.md` para escopo, arquivos alterados e validação.

**Validação V23:** conferência estática dos arquivos alterados e revisão estrutural das regras de responsividade. A compilação completa do frontend e a homologação final no Docker/Windows ainda devem ser executadas localmente antes de produção.


## V24 — Detalhe da O.S. com área de trabalho ampliada no celular (17/11/2026)

- O detalhe da O.S. ocupa a altura útil do celular; **somente o corpo da O.S. tem rolagem vertical**, deixando os dados visíveis em uma área muito maior.
- As abas Edição completa, Dados técnicos, Valores, Materiais, Status, Documentos, Orçamento, Mecânica e Histórico passam a ocupar **uma faixa horizontal deslizável**. A aba ativa é revelada automaticamente.
- O cabeçalho exibe OS, cliente, equipamento e status sem botões grandes ocupando várias linhas. As ações extras ficam em **Ações**, com acesso a receitas, inativação (se permitido) e etiqueta.
- O rodapé possui **Fechar** e **Salvar alterações** na mesma linha, com alvos de toque confortáveis.
- O formulário do orçamento usa campos e seções ajustados para celular, sem obrigar a deslizar horizontalmente para editar componentes. Os dados completos de cliente/equipamento ficam disponíveis em botão expansível, permanecendo normalmente visíveis no desktop.
- A V24 **não** altera a listagem em cartões da V23, a aparência desktop, os perfis, o banco, os volumes Docker ou o instalador único.
- Consulte `ATUALIZACAO_V24_DETALHE_OS_MOBILE_20261117.md` e teste em uma cópia local antes de atualizar a VPS.


## V25 — contador mensal do painel corrigido (17/11/2026)

- Corrigido o card **Equipamentos com entrada em [mês]** no painel mobile.
- O número total agora permanece **sempre na horizontal**, sem quebrar em coluna vertical.
- O contador recebeu largura reservada, números tabulares e bloqueio de quebra de linha.
- Em telas pequenas, o card usa distribuição em duas áreas: texto à esquerda e total à direita.
- Nenhuma alteração de banco, volumes, permissões ou regras de negócio.

**Validação V25:** ajuste CSS direcionado, sem migração de banco. A homologação visual final no Docker/Windows continua recomendada antes de atualizar a produção.


## V26 — Organização do painel por áreas (17/11/2026)

- No **Painel inicial**, use o botão **Personalizar painel** para mostrar ou ocultar áreas disponíveis ao seu perfil: Laboratório, Orçamentos, Compras, Financeiro, Estoque, Notificações e Ações rápidas.
- Cada área permite **Visível/Oculta** e **Somente esta**. O botão **Mostrar tudo** reativa todos os blocos permitidos para o usuário.
- Os indicadores principais e as filas de trabalho também seguem o filtro, não apenas os títulos. O total de entradas do mês acompanha a área Laboratório.
- A escolha fica armazenada **no navegador em uso**, por ID de usuário. Não sincroniza automaticamente entre computadores; não é uma alteração de perfil/permissão nem de banco de dados.
- O acesso pelo sino e pelos módulos permanece disponível mesmo quando uma área do painel está escondida.
- Sem nova migração, mudança de volumes, Docker Compose, funções, finanças ou regras de negócio.

**Verificações V26:** 11 testes das preferências, 45 testes do instalador, 56 arquivos TS/TSX sem falhas sintáticas e arquivos CSS analisados. O build React completo continua dependente das dependências NPM e da homologação no Docker local antes de produção.


## V27 — Temas comemorativos com efeitos (17/11/2026)

- **Carnaval em fevereiro**, **Páscoa no mês correspondente ao ano**, **São João em junho**, **Halloween em outubro** e **Natal em dezembro**.
- Natal com flocos de neve em movimento e luzes coloridas piscando; outras comemorações com ornamentos discretos.
- Novo seletor de **Temas comemorativos** no menu lateral com **Automático**, **Desativado** e **Prévia manual**. Opção para desativar apenas as animações.
- Compatível com tema claro/escuro, modo celular e configuração de movimento reduzido do sistema operacional.
- Sem novas dependências NPM, novas migrações Alembic, alterações no banco, no projeto Docker ou no instalador único.
- Detalhes, arquivos alterados, testes e limitações em `ATUALIZACAO_V27_TEMAS_COMEMORATIVOS_20261117.md`.

## V28 — calendário dos temas comemorativos ajustado (17/11/2026)

- **Natal** agora fica ativo automaticamente em **novembro e dezembro**.
- **Janeiro** ganhou o tema **Ano-Novo**, com **fogos de artifício** como decoração animada.
- O seletor manual de **Temas comemorativos** agora inclui **Ano-Novo (prévia)**.
- As animações continuam opcionais e respeitam a preferência do dispositivo por redução de movimento.
- Nenhuma alteração de banco, volumes, permissões ou regras operacionais do ERP.

**Validação V28:** atualização visual e de calendário, sem migração de banco. A homologação visual final no Docker/Windows continua recomendada antes de produção.


## V29 — temas comemorativos mais ornamentados (18/11/2026)

- **Halloween (outubro):** arte ilustrada com abóboras, esqueleto, doces, caveiras, teias e morcegos, em tons laranja/roxo.
- **Carnaval (fevereiro):** máscara carnavalesca, sombrinhas de frevo, serpentinas, fitas e confetes animados.
- **Ano-Novo (janeiro):** arte com champanhe e taças, fogos de artifício mais destacados e saudação com ano calculado automaticamente (por exemplo, **Feliz 2027!**).
- **Páscoa e São João:** artes integradas ao painel. **Natal** mantém a neve e as luzes coloridas, agora também com uma faixa comemorativa.
- O painel continua com seus indicadores e filtros reais; a nova faixa é um **componente visual funcional**, não uma imagem da tela inteira.
- Decorações globais não interceptam cliques; animações podem ser desligadas em **Aparência → Temas comemorativos** e respeitam preferência de movimento reduzido.
- O tema claro/escuro e todas as correções até a V28 permanecem disponíveis.
- Não há nova migração de banco nem modificação do Compose, volumes ou instalador.

**Verificações V29:** 19 testes de calendário/preferências, 11 testes específicos da decoração, 23 testes de compatibilidade/instalação, 59 arquivos TS/TSX verificados sintaticamente e CSS sem erros de parsing. A compilação integral React/Vite não foi executada (faltam dependências no cache). A prévia visual automatizada no Chromium também não concluiu; homologue a aparência no Docker antes de atualizar a VPS.

## V30 — correção dos rascunhos/revisões de orçamento (23/11/2026)

- Ao gerar **Nova revisão**, o sistema reaproveita um rascunho existente em vez de bloquear o usuário ou obrigá-lo a excluir revisões.
- Salvar um rascunho atualiza itens e valores sem recriar indevidamente registros anteriores; fotos e legendas permanecem vinculadas.
- A interface confirma o valor persistido por uma segunda consulta ao servidor e mostra a quantia final antes de emitir.
- O botão **Salvar e emitir PDF** grava alterações pendentes e exige retorno HTTP de sucesso do servidor; falhas de geração são exibidas dentro da OS.
- A revisão emitida anteriormente é imutável. O novo valor só altera a revisão em rascunho.
- Nenhuma migração de banco, alteração de volumes, alterações na VPS ou necessidade de apagar rascunhos.
- Consulte `ATUALIZACAO_V30_RASCUNHOS_ORCAMENTOS_20261123.md` para o roteiro do teste R$ 25.000 → R$ 22.000.

**Validação V30:** testes de orçamento/revisões/fotos/PDF e do instalador aprovados, análise sintática TS/TSX aprovada. A compilação completa do React/Vite e a homologação real em Docker/PostgreSQL precisam ser executadas no ambiente local antes de produção.


## V31 — filtros de datas no painel por função (23/11/2026)

- Na tela **Painel → Personalizar painel**, escolha **Todo o histórico**, **Este mês**, **Últimos 30 dias**, **Últimos 90 dias**, **Este ano** ou **Escolher datas**.
- Para evitar indicadores de OS antigas de outro sistema, selecione **Escolher datas**, informe a **data inicial** (por exemplo, 01/11/2026) e deixe a data final vazia.
- A API filtra de verdade as contagens e as filas, respeitando as permissões de cada função. Registros antigos não são excluídos do banco e continuam acessíveis nos módulos.
- A preferência de período é salva individualmente neste navegador; o modo inicial é **Todo o histórico** para não ocultar pendências sem a escolha do operador.
- As notificações continuam em tempo real. Sem novas migrações, mudanças de volumes ou alterações no instalador.
- Detalhes, datas de referência por módulo e roteiro de homologação em `ATUALIZACAO_V31_FILTRO_DATA_PAINEL_20261123.md`.

**Validação:** testes dirigidos de consultas/segurança e do instalador aprovados; build integral React/Vite e teste completo no Docker/PostgreSQL ainda pendentes. Faça backup e homologue localmente antes de atualizar a VPS.


## V32 — nova logo do orçamento (23/11/2026)

- A **logo antiga do orçamento** foi substituída pela nova marca enviada pelo usuário.
- A troca foi aplicada no **cabeçalho do PDF** e também na **marca d’água** do orçamento do Laboratório.
- A imagem foi preparada com **fundo transparente** para evitar um bloco preto no documento.
- Não houve alteração de banco, permissões, regras de negócio, volumes Docker ou instalador.

**Validação V32:** substituição dos arquivos gráficos usados pelo gerador de PDF e verificação estática das referências no código. A validação visual final do PDF deve ser feita localmente antes do uso em produção.


## V33 — ajuste da logo do orçamento (23/11/2026)

- A **marca d’água** do orçamento voltou a usar a **logo antiga**.
- A **logo nova** continua no **cabeçalho** do orçamento.
- As **cores originais** da nova logo foram preservadas, mantendo o **preto como preto**.
- O fundo externo escuro foi removido somente ao redor da logo para melhorar a apresentação no cabeçalho, sem alterar os elementos internos pretos.
- Não houve alteração de banco, permissões, regras de negócio, volumes Docker ou instalador.

**Validação V33:** substituição/ajuste dos arquivos gráficos do gerador de PDF e verificação estática das referências no código. A validação visual final do PDF deve ser feita localmente antes do uso em produção.


## V34 — cabeçalho do orçamento ajustado (23/11/2026)

- O **nome da empresa** no cabeçalho do orçamento foi reduzido para não cortar as informações abaixo.
- **CNPJ, telefone e e-mail** ficaram maiores, em **negrito** e na cor **branca**.
- O bloco com **Nº da O.S., Emissão e Validade** ficou maior e com mais destaque visual.
- A distribuição do cabeçalho foi reequilibrada para melhorar a leitura geral do PDF.
- Não houve alteração de banco, permissões, regras de negócio, volumes Docker ou instalador.

**Validação V34:** ajuste do layout do cabeçalho do PDF e verificação estática do gerador. A validação visual final deve ser feita localmente com um orçamento real.


## V35 — cabeçalho do orçamento e total por item (23/11/2026)

- O cabeçalho do PDF foi reorganizado para melhorar a leitura de **ORÇAMENTO PRÉVIO E ESTIMATIVO**.
- O bloco direito do cabeçalho foi reequilibrado, mantendo **Nº da O.S.**, **Emissão** e **Validade** em destaque.
- A tela de edição do orçamento agora exibe a coluna **Total do item** ao lado de **Valor unitário**.
- O total por item é calculado automaticamente por **quantidade × valor unitário**.
- O layout mobile do editor foi ajustado para acomodar a nova coluna.
- Não houve alteração de banco, permissões, regras de negócio, volumes Docker ou instalador.

**Validação V35:** ajuste do layout do PDF, atualização da grade do editor e verificação estática dos arquivos alterados. A validação visual final deve ser feita localmente com um orçamento real.


## V37 — Pesquisa de cliente no cadastro e na edição da OS

- O dropdown convencional foi substituído por uma **caixa de pesquisa com sugestões** em **Nova OS** e **OS existente → Edição completa**.
- Permite buscar por razão social, nome fantasia ou CNPJ, ignorando maiúsculas/minúsculas e acentos.
- A lista de resultados aceita teclado (setas, Enter, Esc), mouse e toque; a seleção vincula o **ID do cliente** já cadastrado.
- A edição mantém o cliente atual até o operador **selecionar outro resultado**, evitando alterações por digitação acidental.
- O cliente sugerido é restrito à **empresa da OS**. Uma mudança da empresa no formulário limpa a seleção para impedir associação indevida.
- Permissões, notificações, orçamentos, notas fiscais, garantia e regras financeiras foram preservados.
- **Sem nova migração de banco**; a migração da V36 ainda será executada se o ambiente estiver em uma versão anterior.

Validações V37: 49 testes do instalador/checagens de integração aprovados, 10 casos reais de pesquisa executados sobre a função TypeScript, e análise sintática dos três arquivos TS/TSX envolvidos. **Build completo React/Vite e homologação no Docker/Windows ainda pendentes**.


## V38 — orientação da pesquisa de clientes na mesma linha (23/11/2026)

- “Digite parte do nome e escolha uma sugestão.” aparece alinhado **à direita** de “Cliente *”, sem ocupar espaço abaixo da pesquisa.
- Aplica-se ao formulário de **Nova OS** e à **Edição completa** de uma OS existente.
- Layout adaptado para o celular e para os temas claro e escuro.
- Nenhuma alteração no funcionamento da busca, seleção, API, banco ou instalador.


## V40 — endereço das empresas emitentes no orçamento

- Comercial → Cadastros → Empresas emitentes: formulário inclui **endereço completo, cidade e UF**.
- Ao selecionar uma empresa, os dados salvos são carregados automaticamente antes de editar; não é mais necessário redigitar outros dados para preencher o endereço.
- O resumo do cadastro exibe o endereço de cada emitente.
- Orçamentos do Laboratório em rascunho e novas emissões mostram o endereço da emitente vinculada à O.S.; as revisões já emitidas preservam seu snapshot histórico.
- Cabeçalho do PDF agora cresce quando necessário para evitar corte de endereços extensos.
- Campos de banco, APIs e permissões existentes foram reaproveitados; **sem migração**.
- Nenhum endereço foi preenchido automaticamente ou inventado: cadastre o endereço real de cada empresa antes de emitir.

**Verificação V40:** 12 testes direcionados de cadastro/snapshot, 23 testes de instalador, três PDFs sintéticos gerados e verificados visualmente e sintaxe TSX analisada. A compilação completa do frontend e a homologação PostgreSQL/Docker estão pendentes de teste no ambiente local.


## V41 — proteção do salvamento de orçamentos (23/11/2026)

- Corrigido o erro visual em que a revisão era recarregada antes de verificar a gravação; o novo valor não desaparece em caso de falha.
- O sistema compara **valor total, subtotal, itens, quantidades, valores unitários, descrição, laudo, condições, desconto e fotos** com a resposta do servidor e com uma nova consulta à API.
- As mensagens de sucesso e falha aparecem no topo da aba Orçamento, sem obrigar o operador a procurar o erro no final do formulário.
- O botão geral do rodapé, quando a aba Orçamento estiver aberta, passa a executar **Salvar orçamento**. Nas outras abas continua executando **Salvar alterações** da OS.
- O campo monetário permite valores em formato brasileiro, como `22.000,00`, ou decimal com ponto, como `22000.00`.
- A resposta atrasada de outra OS ou a leitura inicial não substitui mais uma edição em andamento.
- Nenhuma exclusão de rascunhos, revisão ou fotos é necessária. **Sem migração adicional de banco**.

**Validação V41:** 72 testes automatizados de regressão aprovados, 1 teste de integração pendente por dependência de PostgreSQL; 20 verificações executadas do comparador de gravação; sintaxe TSX verificada. O build completo e a homologação no Docker real ainda precisam ser realizados antes de produção.


## V42 — salvamento de orçamento com confirmação transacional

- A API passa a confirmar em SQL os totais e itens de um rascunho antes de concluir a transação.
- A tela não abandona a edição caso haja divergência; indica valores solicitado/registrado e exige API V42.
- Revisões antigas, PDFs emitidos, fotos, banco e volumes permanecem preservados.
- **Sem migração nova.** Homologar no Docker/PostgreSQL antes de atualizar produção.
