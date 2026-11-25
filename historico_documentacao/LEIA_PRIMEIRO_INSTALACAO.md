> **LEIA PRIMEIRO:** este guia foi substituido por `LEIA_PRIMEIRO_COMPATIBILIDADE_V14.md`, que descreve o instalador atual por estrutura de dados, sem nomes obrigatorios. Os detalhes de nomes fixos abaixo sao historicos.

# SÊNTICO V14 — instalação local com volumes FIXOS ORIGINAIS

## Como iniciar

1. Abra o Docker Desktop em modo Linux.
2. Extraia o projeto completo numa pasta nova. Não misture instalações anteriores.
3. Execute **INICIAR_SENTICO_V14.cmd** (o nome antigo **INICIAR_SENTICO_GREEN.cmd** também chama o mesmo instalador).
4. Quando aparecer `SENTICO_V14_INICIADO=OK`, abra **http://127.0.0.1:5184/**.
5. Entre com um usuário existente. O instalador não cria administrador de testes.

**Nomes Docker imutáveis, idênticos aos da recuperação V14 anterior**:

| Função | Nome exato |
|---|---|
| PostgreSQL 17 | `sentico-v14-recuperado_pgdata` |
| Fotos, documentos e outros uploads | `sentico-v14-recuperado_uploads` |
| Dependências do frontend | `sentico-v14-recuperado_node_modules` |

Identidade fixa do projeto Docker Compose: `sentico-v14-recuperado`. Esses três volumes são `external: true` no arquivo `codigo-fonte/compose.recuperacao.yml`. **Mudar o nome da pasta não muda os volumes.**

## Ordem de recuperação

1. Identifica os volumes **com esses mesmos nomes**, sem renomeá-los.
2. Se o PostgreSQL existente tiver `PG_VERSION=17`, **usa esse volume diretamente**. Não tenta validar o arquivo `.tar.gz` nem copiar outro banco por cima.
3. **Só se o volume estiver ausente ou realmente vazio**, extrai um backup disponível para esse mesmo volume. Nunca sobrescreve um volume preenchido.
4. Inicia PostgreSQL. Identifica um banco real entre `sentico_green`, `sentico_green_preview` e `sentico_green_sync_trial_20261019_01` usando tabelas e revisão Alembic. **Não exige contagens exatas**, pois cadastros podem mudar.
5. Configura/valida a conexão da API, verifica a escrita e aplica as migrations até `20261028_01` somente quando necessário.
6. Inicia interface e gateway no endereço **http://127.0.0.1:5184/**.

Se não houver banco existente e também não houver backup válido, a instalação para sem criar uma base fictícia. Um backup físico inconsistente não é reparável apenas mudando nomes.

## Configuração persistente

O arquivo de configuração fica em `%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao`. O instalador **reutiliza a senha que já existe**; não a substitui toda vez. Não envie esse arquivo nem senhas.

Portas locais fixas: Web `5184`, API `8183`, Vite `5183`, PostgreSQL `5543`. Não afeta VPS ou ambientes Blue/Green.

## Preservação de dados

- Os volumes antigos `sentico-dev-entrega_*` **não são utilizados** nem removidos.
- Os volumes V14 existentes são reutilizados; **as migrations poderão alterar a estrutura do banco V14**. Guarde o backup original para permitir retorno.
- O script não usa `docker compose down -v`, `docker volume rm` nem `docker volume prune`.
- **Não use** `compose.dev.yml` ou scripts antigos isoladamente para essa recuperação. O ponto de entrada correto é `INICIAR_SENTICO_V14.cmd`.
- Se houver falha, envie apenas o código/etapa e logs sem dados de clientes ou credenciais.

## Limitações dos testes

O código foi examinado, scripts shell verificados sintaticamente, pacotes ZIP checados e API compilada. **A execução completa no Docker Desktop do seu Windows não foi reproduzida neste ambiente**. Uma imagem física de PostgreSQL inconsistente ou configurações específicas do Docker local ainda podem causar falha e exigirão o erro detalhado do serviço.
