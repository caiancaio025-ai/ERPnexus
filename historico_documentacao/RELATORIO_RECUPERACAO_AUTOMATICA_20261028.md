# Relatório técnico — Recuperação local V14 (28/10/2026)

## Problema resolvido no instalador

O volume Docker original `sentico-dev-entrega_dev_postgres_data` contém um cluster PostgreSQL 17 de origem Green, com role `sentico_green`, mas o antigo instalador usava `sentico_dev`, base `sentico_dev` e um `.env.dev` ausente. Não era seguro inicializar um novo banco por cima desse volume.

## Base escolhida

`sentico_green_sync_trial_20261019_01`, por conter status mais recente no pedido de compra nº 7 (entregue em 16/10/2026). Dados diagnosticados antes da recuperação: usuários 12, clientes 292, ordens de serviço 1.045, pedidos 8; Alembic `20261013_02`. As tabelas restantes não foram conciliadas integralmente.

## Solução implementada

- Instalador novo com nome compatível com o botão anterior `INICIAR_SENTICO_GREEN.cmd`.
- Restauração do TAR físico selecionado **em volume NOVO**: `sentico-v14-recuperado_pgdata`.
- Alteração da senha da role PostgreSQL `sentico_green` **somente na cópia restaurada**, sem modificar usuários do aplicativo.
- Configuração de conexão à base real `sentico_green_sync_trial_20261019_01`.
- Senha gerada com criptografia segura e armazenada no perfil Windows do usuário: `%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao`; não incluída em ZIP.
- `compose.recuperacao.yml` usa Compose `sentico-v14-recuperado`, portas restritas a localhost e volumes próprios para banco, uploads e node_modules.
- `compose.dev.yml` deste pacote aponta também para o projeto isolado, evitando uso acidental do volume anterior.
- Conta fictícia do desenvolvimento desativada via `SENTICO_DEV_TEST_ACCOUNT=0`.
- Confirmação de totais 12/292/1045/8 antes e depois do upgrade Alembic para `20261028_01`.
- Execução separada de builds para reduzir carga e impedir que uma falha ocultasse outra.
- Preservação dos dados/volumes originais e backups existentes. Nenhum comando de remoção de volumes.

## Testes realmente realizados

- YAML interpretado via PyYAML e identidade dos volumes verificada.
- Verificações estáticas do instalador, URLs e seleção de banco.
- Verificação de sintaxe dos 4 scripts shell com `sh -n`.
- Encadeamento de **11 migrations** entre `20261013_02` e `20261028_01` validado no código-fonte.
- Integridade e conteúdo dos ZIPs verificados (CRC e SHA256).

## Pendências / limitações explícitas

- Não dispomos de Docker Desktop do notebook nem dos arquivos privados do banco; **o fluxo completo de PowerShell, PostgreSQL, Alembic e interface NÃO foi executado neste ambiente**. Se a operação falhar, o instalador interrompe com diagnóstico sem apagar os dados antigos.
- Os arquivos `uploads.tar.gz` reportados pelo usuário ocupavam aproximadamente 0 MB; fotografias e documentos no disco talvez não estejam representados no backup. Deve-se conferir visualmente após a restauração.
- O backend da API acessará o PostgreSQL com a role de origem `sentico_green`, que no backup tem atributo de superusuário. Isso é tolerado somente em recuperação local isolada; **não copiar Compose de recuperação para produção**.
- O comparativo entre os dois bancos foi restrito às contagens e assinaturas de quatro tabelas. Não afirmar identidade completa de todo o esquema e histórico.
- A aplicação das migrations é sobre a cópia restaurada, e deve ser homologada antes de publicar em qualquer servidor.

## Retomada se interromper

Não exclua volumes. Se `sentico-v14-recuperado_pgdata` já existir, o instalador só o aceita se houver um marcador identificando esta recuperação e a configuração persistente de senha. Não restaura o backup outra vez nem redefine senha automaticamente. Em caso de falha no estágio de restauração inicial, preservar os volumes e o texto de erro para correção pontual.
