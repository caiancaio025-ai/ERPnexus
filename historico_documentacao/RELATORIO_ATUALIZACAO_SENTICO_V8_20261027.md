# SÊNTICO ERP — V8 | NF, parcelamento e OS inativa

Base: SÊNTICO V7 Laboratório/Estoque/Gavetas (instalador Docker funcional preservado).
Release: 27/10/2026. Desenvolvida somente no código local; nenhuma mudança aplicada à VPS.

## Escopo implementado

### Laboratório
- Mantidos NF de entrada e NF de saída, acrescentado terceiro campo NF de garantia (até 80 caracteres), nas telas de criação, edição, listagem, API e busca.
- Inativação lógica de OS com motivo obrigatório (mínimo dez caracteres), versão otimista e registros de usuário/hora, conservando o número e histórico. Ação restrita a admin/gestão/super_admin.
- OS inativa deixa a listagem padrão, totais, sugestão de local, mapa físico e relatório de produção. Gestores podem marcar “Mostrar OS inativas” para consultar o histórico.
- Ao inativar, localização física é liberada com histórico. A edição e alteração de status ficam bloqueadas.
- Para segurança, inativação bloqueada caso haja lançamentos financeiros ativos, solicitações de compra de materiais ou movimentações de estoque vinculadas. Não há exclusão física de OS e não existe reativação automática nesta versão.

### Financeiro
- Edição do cronograma de receitas parceladas: vencimentos, valores, inclusão e remoção de parcelas pendentes. Valor total atualizado à soma do novo cronograma, com confirmação prévia.
- Exclusão lógica de todo o parcelamento de receita pendente, auditada; preserva registros, anexos e identificadores no banco.
- Não altera nem exclui parcelas com baixa/recebimento ou competências fechadas. Regras aplicadas na API, não apenas na interface.
- A edição preserva o ID dos lançamentos existentes por `entry_id`, prevenindo troca indevida de comprovantes ao remover parcela intermediária.
- Se o lançamento foi vinculado à OS e todo parcelamento é excluído, o status de faturamento da OS não é revertido automaticamente. Conferir a situação da OS separadamente.

## Banco e instalação

Nova migration Alembic: `20261027_01` (base anterior `20261026_03`).
- Adiciona colunas de NF garantia, situação de inativação, motivo, responsável e data; não exclui dados.
- Antes de atualizar, realizar backup íntegro do PostgreSQL e dos uploads, conferir banco, volumes e configuração `.env.dev` da instalação existente.
- Arquivos `INICIAR_SENTICO_GREEN.cmd` e Compose originais da V7 mantidos. `INSTALAR_SENTICO_DEV.ps1` alterado SOMENTE nas verificações de revisão Alembic para permitir executar a migration nova.
- Não usar `docker compose down -v`; não substituir `.env.dev`; não publicar diretamente na VPS.
- A aplicação da migration em PostgreSQL real exige homologação e backup. O ZIP completo não contém dados reais, segredos ou imagens de clientes.

## Validação disponível
- 78 testes selecionados aprovados (Pydantic, contratos, modelos, fluxos existentes de Laboratório/Financeiro).
- Sintaxe Python e TSX alterados aprovadas.
- Alembic identifica uma cabeça única `20261027_01` e o SQL PostgreSQL offline foi gerado sem SQL de remoção.
- ZIPs conferidos quanto a integridade e conteúdo.

## Validações ainda pendentes
- Build completo Vite/React (node_modules e Vite não disponíveis neste ambiente).
- Testes da API dependentes de psycopg, execução real da migration PostgreSQL e integração com o Docker Desktop.
- Testes ponta a ponta no navegador, perfis/permissões, auditoria e migração de dados reais.
- A versão V8 não está homologada para produção e a VPS permanece inalterada.

## Roteiro de homologação local
1. Cópia de segurança do banco, uploads e código V7, guardando o `.env.dev` em local protegido.
2. Aplicar o patch V7 → V8 apenas no projeto local, reiniciar/reconstruir os serviços normalmente com o instalador original atualizado.
3. Confirmar Alembic `20261027_01`; abrir OS antiga e salvar três NFs.
4. Criar OS fictícia sem movimentações e inativar informando motivo; conferir lista, filtro de inativas, histórico, mapa e totais.
5. Tentar inativar OS com financeiro ou estoque vinculados: deve bloquear.
6. No Financeiro, cadastrar receita parcelada fictícia; alterar vencimento e valor, acrescentar parcela, excluir parcela intermediária com anexo e conferir identidade/auditoria.
7. Testar bloqueios após baixar parcela e fechar competência; validar relatório, valores e anexos.
8. Só considerar VPS após validações completas, plano de rollback e backup restaurável.
