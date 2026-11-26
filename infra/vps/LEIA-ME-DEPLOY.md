# SÊNTICO Green — atualizar a VPS da V47 para a V48

Atualizador preparado em **26/11/2026** para a instalação existente em `/opt/sentico-green`, com projeto Docker `sentico-green-hml`, volumes de PostgreSQL e uploads existentes e esquema Alembic `20261123_02`.

## Comando no terminal da Hostinger

Execute como **root**:

```bash
cd /opt/sentico-green &&
git pull --ff-only origin main &&
bash infra/vps/atualizar.sh
```

O `git pull` baixa também o atualizador novo. Executar uma cópia antiga de `atualizar.sh` antes desse passo ainda pode chamar o procedimento V47.

Acompanhe o terminal até o resultado. A compilação acontece enquanto a versão anterior continua disponível. Depois há um período de manutenção para concluir o backup e trocar a aplicação. Execute em um intervalo adequado para os usuários.

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
3. Inicia uma API temporária sem portas publicadas nem aliases do serviço. Confirma a V48, o destino do banco em conexão somente leitura e as permissões de uploads sob o usuário da nova imagem. Os arquivos de teste são exclusivos e removidos ao terminar.
4. Verifica espaço aproximado para o backup, ativa HTTP 503 temporário no gateway e para a API que recebe gravações. O PostgreSQL continua em execução. Gera backup do banco e dos uploads, lê integralmente o dump sem restaurá-lo e valida o arquivo de uploads e seus hashes.
5. Atualiza a tag em `.env.production`/`.tag` e recria somente API e interface. Banco, gateway, volumes e redes existentes são preservados. **Não executa migração ou downgrade de esquema.**
6. Confere a revisão do banco, IDs das imagens, saúde, versão 48, HTML e hashes dos arquivos iniciais da interface através do gateway. Essas consultas usam uma autorização temporária enquanto os demais acessos permanecem em manutenção. Restaura a configuração anterior do gateway e verifica o domínio público.

## Falha durante a atualização

- **Antes da troca:** preserva a aplicação anterior. Se a API havia sido parada para o backup, tenta reiniciá-la e retirar a manutenção somente depois da conferência de saúde.
- **Durante a troca ou conferência interna:** reaplica a manutenção, restaura a configuração e retorna API/interface às imagens anteriores. Confere os IDs e a saúde antes de liberar o acesso.
- **Retorno não confirmado:** mantém a manutenção quando possível e informa `RETORNO_APLICACAO_ANTERIOR=FALHOU`, com o diretório dos registros. Não tenta restaurar o banco por cima de dados existentes.
- **Somente a confirmação pública falhou:** informa `V48_INTERNA=OK` e `ACESSO_PUBLICO=NAO_CONFIRMADO`, com código de saída 2. A V48 validada internamente permanece ativa; o proxy externo/DNS deve ser conferido. Esse resultado não deve ser tratado como confirmação do acesso público.

Em uma interrupção, preserve a saída do terminal e os arquivos no diretório informado em `REGISTROS` ou `BACKUP`. O diretório contém credenciais de recuperação: mantenha-o privado e não o publique no GitHub.

O script não remove volumes, não recria o PostgreSQL e não executa restauração automática de dados. Ele não usa `infra/vps/voltar.sh`, que continua sendo um bloqueio legado. O procedimento V47 original está preservado para consulta em `infra/vps/historico/`.

## Validação e limites

O script é verificado com Bash/Git reais e um simulador de Docker/HTTP em diretórios descartáveis, exercitando sucesso, falhas de preflight e backup, troca parcial, retorno das imagens, repetição do mesmo commit e falha de confirmação pública. Os helpers possuem testes de preservação de configuração, arquivos e validações.

A configuração de manutenção, o bypass temporário e a restauração foram testados com **Caddy 2.10.2 real**. A verificação de banco também foi exercitada com PostgreSQL descartável. Foram aprovados 15 cenários Bash/Git, 72 testes do helper, 11 verificações com Caddy e cinco casos com PostgreSQL. O [resumo das execuções](../../validacao_v48/deploy-vps-resumo.json) distingue os componentes reais dos simulados e registra os arquivos verificados.

**A execução Docker na VPS da Hostinger ainda precisa ser feita pelo comando acima.** Os testes locais não representam uma implantação já realizada no servidor. O atualizador realiza suas verificações de ambiente antes de interromper a aplicação.

Para repetir os testes do atualizador em um ambiente de desenvolvimento com Git, Bash, Python e pytest:

```bash
python -m pytest infra/vps/tests -q
bash -n infra/vps/atualizar.sh
```

A regressão PostgreSQL real só é executada quando `DATABASE_URL` e `SENTICO_TEST_DATABASE_URL` apontam explicitamente para o mesmo banco descartável, com nome terminado em `_test` e esquema atual. Sem esse ambiente, esse teste é marcado como ignorado.

Referências técnicas: [Docker Compose run](https://docs.docker.com/reference/cli/docker/compose/run/), [Caddy reload](https://caddyserver.com/docs/command-line#caddy-reload) e [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).
