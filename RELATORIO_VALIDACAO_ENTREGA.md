# RELATÓRIO DE VALIDAÇÃO DA ENTREGA — 21/10/2026

## Objetivo
Auditar as duas entregas recebidas e fornecer um pacote fonte portátil, mais seguro para desenvolvimento externo.

## Pacote original
- `SENTICO_GREEN_DEV_COMPLETO.zip` e `SENTICO_GREEN_DEV_COMPLETO_README_CORRIGIDO.zip`: **CRC íntegro** em todas as entradas.
- Arquivo Docker OCI `sentico-green-images.tar`: TAR íntegro, manifestos para API e Web e SHA256 de todos os blobs verificados.
- A integridade estrutural não comprova funcionamento dos serviços nem confidencialidade dos conteúdos.

## Problemas comprovados e correções
1. **Dados operacionais reais:** removidos os **12** arquivos históricos de `apps/api/scripts/finance_reconcile_data/`, incluindo CSVs com fornecedores, clientes, notas e valores. O código do Financeiro permanece incluído. A ausência desses datasets impede reexecutar conciliações históricas dependentes deles, por segurança.
2. **Imagem Docker anterior à sanitização:** excluído `sentico-green-images.tar` (119,710,208 bytes). A imagem API foi construída antes da substituição de dados cadastrais presentes no código. O Compose de desenvolvimento não dependia dessas imagens: ele **constrói localmente**, portanto a exclusão não retira os módulos. A nova versão não é uma reprodução binária da imagem de produção.
3. **Erro de build da Web:** `apps/web/Dockerfile.dev` continha `COPY .npmrc ...`, mas `.npmrc` não existia no ZIP. Corrigido para copiar apenas `package.json` e `package-lock.json`.
4. **Dockerfile Web de produção incompleto:** `apps/web/Dockerfile` exigia um `Caddyfile` ausente. Acrescentado Caddyfile estático correspondente à configuração `/srv` e porta 8080 extraída do container de referência; não altera o gateway de desenvolvimento.
5. **README raiz desatualizado:** continha instruções para Compose genérico, criação de `.env` e `alembic upgrade head` em banco vazio. Substituído por referência explícita ao manual auditado.
6. **Portabilidade do ZIP:** o pacote original tinha entradas com separadores `\` do Windows. As entradas da nova versão utilizam `/`, compatíveis com extratores Windows/Linux/macOS.
7. **BOM Python:** normalizados os dois arquivos `apps/api/tests/conftest.py` e `apps/api/migrations/versions/20261007_01_finance_accounts_by_company.py` (UTF-8 com BOM), evitando inconsistências de parsers e linters.
8. **Documentação:** roteiro de criação do administrador, migration `20261009_01` → usuário → `head`, portas, logs, limitações e segurança revisados. Guia incluído dentro e fora do ZIP.

## Verificações realizadas neste ambiente
- Parser AST: **177 arquivos Python** analisados, sem erro de sintaxe.
- JSON: **5 arquivos** analisados.
- TOML: **1 arquivos** analisados.
- `package.json` e `package-lock.json`: dependências e devDependencies da raiz compatíveis, lockfile V3.
- Arquivos do Compose e das construções locais: caminhos essenciais presentes.
- Scan heurístico para chaves privadas e determinados tokens: **sem ocorrências** (não é auditoria completa de segurança).
- Arquivos `.env` reais, dump de produção, datasets financeiros e imagem original: não entregues.
- Nenhum arquivo do projeto original foi alterado; só uma nova cópia foi preparada.

## Limitações explícitas
**Não foi possível executar Docker ou construir os containers neste ambiente de auditoria.** Portanto build `npm ci`, instalações pip, aplicação de migrations, login, end-to-end e regressão funcional precisam ser homologados na máquina do destinatário. Não interpretar verificação estática ou CRC como aprovação funcional absoluta.

## Segurança adicional
O ZIP contém código proprietário e artefatos da empresa mesmo sem banco: compartilhar somente com pessoa autorizada. Um arquivo `.env.example` é apenas modelo e não contém segredo efetivo. As imagens originais de produção devem ser preservadas apenas nos ambientes autorizados, não no pacote público.
