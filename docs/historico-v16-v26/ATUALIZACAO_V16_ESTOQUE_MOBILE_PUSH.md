# SÊNTICO V16 — Estoque, experiência mobile e notificações Web Push

**Base:** pacote V15 fornecido pelo usuário em 16/11/2026. **Estado:** código implementado; testes estáticos e de compatibilidade do instalador executados. Não foi feita atualização na VPS, nem homologação real em Windows/iOS/Android ou emissão de push de ponta a ponta.

## Funcionalidades

1. **Estoque → Novo item → Posição física:** o antigo seletor `select` foi substituído por pesquisa com autocomplete e navegação por teclado. Busca por código da posição, área, nome da estante, caixa, gaveta ou tipo. O `slot_id` persistido pela API é o mesmo; não há alteração das regras de estoque nem criação automática de novos endereços.
2. **Mobile (< 768 px):** regras CSS exclusivas de telas pequenas para tamanho de inputs que não causam zoom automático no iPhone, formulários de uma coluna, diálogos roláveis, alvos de toque maiores e largura adequada. O desktop não recebe essas regras.
3. **Web Push:** novas inscrições por navegador/dispositivo, service worker de notificação sem cache de dados do ERP, fila no PostgreSQL após commit e envio opcional para os dispositivos autorizados do usuário. A notificação aparece no Windows/Android/iOS compatível (apenas com HTTPS e permissão), abre a central no painel ao clicar e mantém a notificação detalhada dentro do ERP.
4. **Aplicativo instalado no PC:** o controle identifica computador ou celular e permite ativar ou desativar as notificações por dispositivo. Uma PWA instalada pelo **Microsoft Edge ou Google Chrome** pode apresentar notificações nativas do Windows, inclusive com a janela fechada se o navegador e o sistema permitirem tarefas em segundo plano. **Não significa que um .exe próprio baseado em WebView2 receba push fechado**; isso exige implementação nativa específica e seu código-fonte não faz parte do ZIP.
5. **Privacidade:** mensagens do sistema operacional são genéricas; valores, clientes e detalhes de OS não são expostos na tela bloqueada. Ao sair da sessão pelo aplicativo, a inscrição do dispositivo é revogada (outros dispositivos do usuário não são afetados).

## Instalação local / homologação

- Faça **backup dos dados e dos uploads**. Não execute `docker compose down -v` nem apague volumes.
- Extraia o novo ZIP por completo; execute apenas `INICIAR_SENTICO.cmd` no Windows com Docker Desktop, conforme `LEIA_PRIMEIRO_SENTICO.md`. O instalador reconhece a nova revisão Alembic `20261116_01` e o esquema anterior `20261112_01`.
- Verifique no laboratório local a integridade das funcionalidades existentes antes de qualquer VPS. A nova migração cria `notification_push_subscriptions` e adiciona `notifications.push_processed_at`; não altera registros de estoque, financeiro ou OS.
- Push não estará ativo até configurar uma **chave VAPID** para o ambiente. Em `codigo-fonte/apps/api`, use `python -m app.notifications.vapid_keys --output-dir <pasta segura>` em ambiente com dependências instaladas. Não inclua a chave privada em repositórios, ZIPs, e-mails ou mensagens.
- Para o Compose local, guarde a chave privada em `codigo-fonte/secrets/sentico-vapid-private.pem` (fora do pacote; diretório montado somente leitura) e configure `PUSH_VAPID_PUBLIC_KEY` e `PUSH_VAPID_SUBJECT=mailto:email-valido@dominio.com` no `.env.recuperacao` que o instalador usa. Reinicie somente a API após configurar, preservando o banco. Mantenha a chave privada idêntica em todas as réplicas da API.
- Na VPS, instale e configure o serviço conforme o **Compose de produção efetivamente em uso**, que não foi fornecido neste pacote. Esse serviço deve receber as mesmas variáveis VAPID e acessar a chave PEM por montagem segura. Exige HTTPS público e saída de rede aos provedores de push (FCM, APNs, WNS, Mozilla). Não copie o Compose local para a VPS.

## Procedimento de teste de push no Windows

1. Acesse o site HTTPS do SÊNTICO pelo Edge ou Chrome em um Windows 10/11 compatível.
2. Instale a aplicação pelo menu do navegador (Aplicativos → Instalar este site como aplicativo) e entre na conta.
3. No painel, abra o sino de notificações e selecione **Ativar notificações neste computador**. Aceite a permissão do navegador e do Windows.
4. Em outra sessão autorizada, execute uma ação que já gera notificação interna para aquela conta, por exemplo um orçamento aprovado, e confirme o evento na central do ERP.
5. Feche a **janela** da PWA e confirme se o Windows entrega o alerta; verifique Assistente de Foco / Não Perturbe, configurações de notificações e execução em segundo plano do Edge/Chrome.
6. Clique na notificação: deverá abrir o app em `/painel?notificacoes=1`. Verifique que outros computadores/celulares cadastrados também receberam alertas.
7. Clique **Sair** e confirme que aquele dispositivo não recebe mais avisos daquela sessão. Efetue testes separados no Android e no iPhone adicionado à tela inicial.

## Limitações de validação nesta entrega

- Os testes Python de compatibilidade do instalador passaram. A compilação frontend integral e o envio Web Push real ainda precisam ser realizados com dependências NPM, PostgreSQL e rede/HTTPS; esses componentes não estavam disponíveis para testes de ponta a ponta neste ambiente.
- O comportamento de qualquer aplicativo desktop **.exe** WebView2 é diferente de uma PWA instalada pelo navegador e depende do código do executável, não incluído no arquivo recebido.
- Não substitui backup/homologação em Windows nem justifica implantação direta em produção. Atualize primeiro o ambiente local de testes.
