# SÊNTICO V14 - correção da inspeção do volume Docker

## Falha identificada
A instalação anterior exigia **exatamente uma linha de saída** do `docker run` e mascarava todos os erros com `ERRO_INSPECAO_VOLUME_SEM_MUDAR_DADOS`. Avisos normais do Docker faziam a etapa abortar.

## Ajuste
- Usa `scripts_recuperacao/estado_volume_v14.sh` para devolver um marcador estruturado de PGDATA 17 válido, vazio ou inesperado.
- Separa o marcador de avisos secundários; falhas reais agora mostram código e resumo do erro do Docker.
- O comando de inspeção é `--network none` e monta `/dados` **readonly**, sem entrar no PostgreSQL ou modificar o volume.
- Permite baixar a imagem oficial do PostgreSQL se ausente (`--pull=missing`).
- Mantém os nomes **imutáveis**: `sentico-v14-recuperado_pgdata`, `sentico-v14-recuperado_uploads`, `sentico-v14-recuperado_node_modules`.
- Nunca executa `docker volume rm`, `docker compose down -v`, `docker system prune` ou restaura backups sobre volume preenchido.

## Uso
1. Com o Docker Desktop aberto, na pasta do projeto extraído, execute `INICIAR_SENTICO_V14.cmd`.
2. A etapa 03 deverá mostrar `VOLUME_POSTGRESQL_ESTADO=PG_VERSION=17` se o PGDATA estiver válido.
3. Caso falhe, copie **apenas a mensagem `ERRO_INSPECAO_VOLUME_DOCKER`** (sem enviar arquivos de banco, `.env` ou senhas). A mensagem agora diferencia imagem ausente, Docker indisponível, permissões e falha na montagem.
4. Preserve os volumes originais `sentico-dev-entrega_*` e V14. As migrations da V14 modificam somente o banco V14 após o preflight e devem ser executadas apenas com backup preservado.

## Limitação
Os testes de sintaxe e de contrato do instalador não substituem um teste real no Docker Desktop do computador do usuário. A autenticação e as migrations continuam sendo etapas distintas que podem revelar outras falhas locais.
