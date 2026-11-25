# Relatório técnico — V14, identidade Docker estável

**Sintoma observado:** o instalador com novos volumes `sentico_v14_local_*` rejeitava os arquivos `banco_postgresql.tar.gz` e `sentico-v14-recuperado_pgdata.tar.gz` com `ERRO_BACKUP_NAO_INICIALIZA`, embora um volume V14 pré-existente já tivesse inicializado antes e permitido acesso ao banco `sentico_green`.

**Causa funcional confirmada no código anterior:** a rotina anterior ignorava o volume `sentico-v14-recuperado_pgdata` e criava os nomes `sentico_v14_local_*`; na ausência desse novo volume, exigia inicializar o backup em um container efêmero e validava contagens fixas de dados. O teste `pg_ctl` descartava o log e produzia somente `ERRO_BACKUP_NAO_INICIALIZA`. Assim, o instalador barrava mesmo com um banco V14 persistente separado dos novos nomes. A causa específica da rejeição da inicialização do backup **não foi comprovada**, pois não há log de PostgreSQL desse subprocesso no relatório do usuário.

## Mudanças efetivadas

- Reutilizado projeto Compose **`sentico-v14-recuperado`** e volumes V14 originais **`sentico-v14-recuperado_pgdata`**, **`sentico-v14-recuperado_uploads`**, **`sentico-v14-recuperado_node_modules`**.
- Volumes declarados `external: true` para impedir nomes compostos por prefixos da pasta.
- Instalador agora prioriza volume PostgreSQL existente com `PG_VERSION=17` e inicia diretamente, sem teste de backup descartável.
- Arquivo `.tar.gz` só é importado quando o volume exato está ausente ou vazio; não se tenta sobrescrever dados.
- Detecta o banco existente por estrutura e revisão Alembic, sem fixar contagens 12/292/1045/8.
- Reutiliza `%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao`.
- Autenticação TCP, validação de escrita, revisão Alembic e `upgrade head` mantidos com barreiras de segurança.
- Correção de read-only limitada à role e ao banco V14 quando o teste de escrita responder `ERRO_API_READ_ONLY`.
- Portas recuperadas de modo estável: gateway 5184, API 8183, web 5183, PostgreSQL 5543.

## Escopo

A instalação reutiliza/atualiza o banco **V14**. Não toca no volume original `sentico-dev-entrega_dev_postgres_data` ou na VPS. Não cria um banco vazio simulando dados da empresa. Não remove volumes e não executa `down -v`.

## Limitação de homologação

O ambiente disponível aqui não dispõe de Docker Desktop Windows; não foi possível provar a execução end-to-end com a base local do usuário. O código e os scripts puderam ser inspecionados e verificados estaticamente. Não declarar a instalação como funcional no notebook até o `SENTICO_V14_INICIADO=OK` ser observado.
