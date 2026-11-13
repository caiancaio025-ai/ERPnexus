> **Instalador atual:** use apenas `INICIAR_SENTICO.cmd` na raiz do pacote. Este documento descreve versões antigas e foi mantido para referência histórica. Veja `LEIA_PRIMEIRO_SENTICO.md`.

> **V4 — 26/10/2026:** integra solicitações avulsas e materiais de OS à entrada de Estoque, com destino opcional antes da chegada e obrigatório em **Recebido**. Migration incremental `20261026_02`. Instalador `INICIAR_SENTICO_GREEN.cmd` na raiz do ZIP. Não enviar para a VPS sem homologação.

> **Atualização 26/10/2026:** este pacote contém as migrations de Estoque até `20261026_01`. Para instalação local, usar `INICIAR_SENTICO_GREEN.cmd` na raiz do ZIP, ou seguir `LEIA_PRIMEIRO_INSTALACAO.md`. O destino de estoque do pedido é opcional até o recebimento físico, obrigatório ao marcar Entregue. Não execute as migrations na VPS sem homologação.

> **Atualizacao do kit com instalador (22/10/2026):** use `INICIAR_SENTICO_GREEN.cmd` na raiz do pacote. Ele pre-cadastra automaticamente o usuario **adm**, senha **123**, e-mail ficticio `adm@.com.br` no banco local e conclui migrations. Instrucoes antigas para cadastrar um administrador manualmente aplicam-se somente a instalacao manual sem o instalador. Nao usar essas credenciais em producao.

# SÊNTICO Green — Entrega de desenvolvimento (22/10/2026)

O kit **agora inclui instalador unico** na raiz do ZIP:

- `../INICIAR_SENTICO_GREEN.cmd`: clique duplo no Windows.
- `../INSTALAR_SENTICO_DEV.ps1`: inicializador PowerShell, com verificacoes de identidade e migracoes.
- `../VERIFICAR_SENTICO_GREEN.cmd`: status dos containers e da revisao Alembic.
- `../LEIA_PRIMEIRO_INSTALACAO.md`: instrucoes detalhadas.

O pacote fonte foi exportado de `c515372`, com sanitizacao de dados e correcoes de portabilidade Docker. Sem imagens binárias da produção, dumps, credenciais ou CSVs financeiros historicos. Os modulos originais permanecem para desenvolvimento.

**O que o instalador executa:** valida o Docker Linux, preserva ou cria `.env.dev`, compila e sobe o projeto Docker `sentico-dev-entrega`, confirma identidade do PostgreSQL, detecta senha divergente e altera apenas a senha do role local, confirma Alembic, aplica `20261009_01`, solicita um administrador ficticio de 12+ caracteres e avanca ao `head` (`20261013_02`). Por fim testa HTTP 200 no gateway, Web e API.

**Endereco:** http://127.0.0.1:5184/

**Cuidado:** o novo instalador foi revisto estaticamente, mas nao foi executado ponta a ponta nesta maquina de elaboracao. Se falhar, ele interrompe preservando volumes. Nao usar em VPS nem em producao.
