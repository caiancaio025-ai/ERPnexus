# SÊNTICO Green — atualizar a VPS para a V48

Atualizador preparado para a instalação existente em `/opt/sentico-green`, com projeto Docker `sentico-green-hml` e volumes de PostgreSQL e uploads existentes. Aceita o esquema Alembic **`20261123_02`** ou **`20261126_01`** e entrega exatamente `20261126_01`, necessário para receber várias unidades individuais da mesma compra/solicitação. Outras revisões são bloqueadas antes da compilação e da parada da aplicação.

## Comando no terminal da Hostinger

Execute como **root**:

```bash
cd /opt/sentico-green &&
git pull --ff-only origin main &&
bash infra/vps/atualizar.sh
```

O `git pull` baixa também o atualizador novo. Executar uma cópia antiga de `atualizar.sh` antes desse passo ainda pode chamar o procedimento V47.

Acompanhe o terminal até o resultado. A compilação e a primeira conferência da nova API acontecem enquanto a versão anterior continua disponível. Depois há um período de manutenção para criar o backup, restaurá-lo em uma cópia isolada, ensaiar a migração, atualizar o banco existente e trocar a aplicação. O tempo depende do tamanho do banco e dos uploads; execute em um intervalo adequado para os usuários.

No sucesso, o final informa:

```text
SENTICO_V48_ATUALIZADO=OK
COMMIT=...
TAG=v48-...
BACKUP=/root/backups-sentico/v48-...
SITE=https://erp.universoeletronica.com/
```

Depois abra o sistema e use **Ctrl+F5**. O endereço `https://erp.universoeletronica.com/api/health/version` deve informar `"version":"48"`.

## O que acontece automaticamente

1. Verifica root, ferramentas (incluindo Python 3.9+), lock de atualização, branch `main` limpa e sincronizada, containers atuais, volumes e revisão do banco. Se o estado não corresponder à instalação esperada, interrompe antes de trocar o sistema.
2. Registra as imagens realmente em uso e a configuração anterior em um diretório restrito. Constrói API e interface V48 com uma tag exclusiva por execução; uma repetição não sobrescreve a tag anterior.
3. Inicia uma API temporária sem portas publicadas nem aliases do serviço. Confirma a V48 e a identidade/revisão atual do banco em conexão somente leitura. Confere as permissões de uploads sob o usuário da nova imagem; os arquivos de teste são exclusivos e removidos ao terminar.
4. Verifica espaço aproximado para o backup e a cópia do PostgreSQL, ativa HTTP 503 temporário no gateway e para a API que recebe gravações. O PostgreSQL de produção continua em execução. Gera backup do banco e dos uploads, lê integralmente o dump e valida o arquivo de uploads e seus hashes.
5. Cria um PostgreSQL descartável com a mesma imagem do banco atual, credenciais temporárias, volume anônimo e rede interna exclusivos da execução. Não publica portas nem conecta essa cópia à rede ou aos volumes de produção. Restaura o dump com interrupção em qualquer erro e compara os registros de estoque da cópia com a origem.
6. Quando necessário, executa **somente `alembic upgrade 20261126_01`** na cópia. Confere a revisão, a coluna `receipt_unit_index`, seu valor padrão e as restrições de unicidade/índice positivo. Compara hashes de todas as colunas anteriores, contagens, quantidades e custos de `inventory_items` e `inventory_movements`; nos históricos, o novo índice deve ser `1`. O ensaio é removido após a conferência.
7. Somente após o ensaio aprovado, com a API antiga ainda parada e o backup validado, aplica a mesma revisão ao banco existente e repete as conferências de preservação. Se o banco já está em `20261126_01`, valida a cópia e o esquema sem reaplicar a migração. Registra as revisões anterior e final em `revisao-final.txt`.
8. Atualiza a tag em `.env.production`/`.tag` e recria somente API e interface. Banco, gateway, volumes e redes de produção existentes são preservados. Confere IDs das imagens, saúde, versão 48, HTML e hashes dos arquivos iniciais através do gateway. Essas consultas usam uma autorização temporária enquanto os demais acessos permanecem em manutenção. Restaura a configuração anterior do gateway e verifica o domínio público.

A migração adiciona o índice de unidade com padrão `1` e troca as duas restrições de origem única por origem mais índice. Não recria tabelas, não renumera itens e não altera quantidades, custos ou vínculos históricos. O volume anônimo do PostgreSQL de ensaio é removido pelo `--rm` do container; o script remove somente a rede temporária que ele próprio criou.

## Falha durante a atualização

- **Antes da migração real:** preserva a revisão anterior. Uma falha de restauração, migração ou comparação na cópia descarta o ensaio e tenta reiniciar a API anterior. A manutenção só é retirada após a conferência de saúde.
- **Na migração real ou depois dela:** verifica a revisão efetivamente confirmada. Se o commit já ocorreu, mantém `20261126_01`; não executa downgrade nem restaura dados. Retorna a aplicação anterior, verifica sua saúde e a preservação do estoque antes de liberar o acesso. Uma falha no comando após o commit não faz o script presumir que o banco voltou à revisão antiga.
- **Durante a troca ou conferência interna:** reaplica a manutenção, restaura a configuração e retorna API/interface às imagens anteriores. Confere os IDs, a saúde e o estado do banco antes de liberar o acesso.
- **Retorno não confirmado:** mantém a manutenção quando possível e informa `RETORNO_APLICACAO_ANTERIOR=FALHOU`, com o diretório dos registros. Não tenta restaurar o banco por cima de dados existentes.
- **Somente a confirmação pública falhou:** informa `V48_INTERNA=OK` e `ACESSO_PUBLICO=NAO_CONFIRMADO`, com código de saída 2. A V48 validada internamente permanece ativa; o proxy externo/DNS deve ser conferido. Esse resultado não deve ser tratado como confirmação do acesso público.

Em uma interrupção, preserve a saída do terminal e os arquivos no diretório informado em `REGISTROS` ou `BACKUP`. O diretório contém credenciais de recuperação: mantenha-o privado e não o publique no GitHub.

O script não remove volumes de produção, não recria o PostgreSQL existente e não executa restauração automática sobre os dados existentes. Ele não usa `infra/vps/voltar.sh`, que continua sendo um bloqueio legado. O procedimento V47 original está preservado para consulta em `infra/vps/historico/`.

As imagens anteriores conseguem ler o esquema aditivo e gravar recebimentos legados com o índice padrão `1`. Depois que usuários começarem a criar grupos de unidades na versão nova, a aplicação anterior não oferece a conciliação completa desses grupos entre SC e PC. O retorno automático durante a implantação verifica que os registros de estoque ainda correspondem ao estado anterior; se houver divergência, mantém a manutenção e exige diagnóstico, preservando os dados. Não use um downgrade de esquema como procedimento de retorno.

## Validação e limites

O script é verificado com Bash/Git reais e um simulador de Docker/HTTP em diretórios descartáveis, exercitando sucesso, falhas de preflight e backup, falhas de restauração e migração na cópia, falha na migração real antes/depois do commit, troca parcial, retorno das imagens com esquema novo, repetição do mesmo commit e falha de confirmação pública. Os helpers possuem testes de preservação de configuração, arquivos, restrições de estoque e hashes dos registros.

A configuração de manutenção, o bypass temporário e a restauração foram testados com **Caddy 2.10.2 real**. O [resumo desta atualização](../../validacao_v48/atualizacao-deploy-resumo.json) registra os resultados atuais: **23 cenários Bash/Git do atualizador**, **90 testes de helpers com PostgreSQL 17 real** e **cinco conferências de dump/restauração/migração com PostgreSQL 16.2 e clientes 16.2 correspondentes**. Os oito cenários afetados pelo guard final de retorno foram reconferidos; o instalador passou 64 testes.

O ensaio adicional executou `pg_dump`, restauração estrita em outro banco descartável e a migração de registros antigos preenchidos, com hashes idênticos antes/depois, índices históricos preservados e duplicados bloqueados. Esse ensaio de dump/restauração usa PostgreSQL 16; a revisão e as restrições dos helpers foram verificadas separadamente no PostgreSQL 17. Docker e a VPS continuam sendo componentes simulados/não executados nessa validação local.

**A execução Docker na VPS da Hostinger ainda precisa ser feita pelo comando acima.** Os testes locais não representam uma implantação já realizada no servidor. O atualizador realiza suas verificações de ambiente antes de interromper a aplicação.

Para repetir os testes do atualizador em um ambiente de desenvolvimento com Git, Bash, Python e pytest:

```bash
python -m pytest infra/vps/tests -q
bash -n infra/vps/atualizar.sh
```

As regressões PostgreSQL reais só são executadas quando `DATABASE_URL` e `SENTICO_TEST_DATABASE_URL` apontam explicitamente para o mesmo banco descartável, com nome terminado em `_test` e esquema atual. Sem esse ambiente, esses testes são marcados como ignorados.

Referências técnicas: [Docker Compose run](https://docs.docker.com/reference/cli/docker/compose/run/), [Caddy reload](https://caddyserver.com/docs/command-line#caddy-reload) e [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).
