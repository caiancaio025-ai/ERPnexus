# SÊNTICO V37 — Pesquisa de cliente na OS

## Objetivo
Simplificar a escolha de clientes quando existem muitos cadastros com nomes semelhantes e permitir corrigir o cliente de uma OS existente com a mesma facilidade.

## Alterações

### Cadastro de uma nova OS
- O campo **Cliente** agora é pesquisável.
- Exemplo: digitar **Capri** filtra o cadastro para mostrar **Capriche**, se estiver cadastrado na empresa escolhida.
- É possível pesquisar por **nome fantasia, razão social e CNPJ**.
- Clique ou toque no resultado; também é possível navegar com **setas**, escolher com **Enter** e fechar com **Esc**.
- Para criar a OS, é obrigatório selecionar um cliente efetivo. Apenas digitar o nome não cria nem seleciona um cadastro.

### Edição de uma OS existente
- Em **Laboratório → OS → Edição completa**, o campo **Cliente** usa o mesmo seletor.
- Pesquisar não troca o cliente até que um resultado seja selecionado.
- A escolha atualiza o **ID e o nome do cliente** da OS; **Salvar alterações** persiste a correção.
- O seletor lista apenas clientes da empresa selecionada; quando a empresa da OS é alterada, o cliente é desmarcado para evitar inconsistência.
- A API de OS existente mantém a validação de que o cliente pertence à empresa e continua preservando as regras de versionamento.

### Visual e acessibilidade
- Campo confortável para uso no celular, sem aumentar o zoom.
- Sugestões com nome fantasia, razão social e documento quando disponíveis.
- Compatível com temas claro e escuro.

## Arquivos modificados
- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/components/CustomerSearchSelect.tsx` (novo)
- `codigo-fonte/apps/web/src/features/laboratory/components/customerSearch.ts` (novo)
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `codigo-fonte/apps/web/src/shared/theme/light-theme.css`
- `testes_instalador/test_v37_cliente_pesquisa.py` (novo)

## Banco e implantação
- **Sem nova migração Alembic:** mantém a revisão `20261123_01` da V36.
- **Sem alteração de volumes, serviços, permissões ou instalador.**
- A versão **V37 inclui a migração da V36**, caso você ainda não a tenha instalado; faça backup de banco e uploads antes da primeira execução.

## Teste de homologação
1. Extraia o ZIP em uma pasta nova e execute `INICIAR_SENTICO.cmd`, com Docker Desktop aberto.
2. No Laboratório, clique em **Nova OS** e selecione a empresa.
3. No campo **Cliente**, digite `Capri`. Escolha o cadastro de **Capriche** (se existente).
4. Preencha os demais campos obrigatórios, salve a OS, feche e abra novamente; confirme que o cliente escolhido permanece.
5. Em **Edição completa**, procure outro cliente, selecione e clique em **Salvar alterações**. Feche e reabra para confirmar.
6. Teste pesquisa sem resultados, mudança de empresa, campo obrigatório, setas + Enter e o uso no celular.
7. Confira os temas claro e escuro e o funcionamento das outras abas da OS.

## Verificações
- 49 testes de instalador/integração estática aprovados.
- 10 casos executados diretamente sobre a função TypeScript (busca por fragmento, acentos, CNPJ, empresa, inativos, ordenação).
- Análise sintática TypeScript/TSX aprovada nos arquivos editados.
- Build completo React/Vite, gravação integrada no PostgreSQL e homologação visual no Docker **pendentes**.
