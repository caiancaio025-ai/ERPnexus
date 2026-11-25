# SÊNTICO V30 — Correção do salvamento e emissão dos orçamentos

**Data:** 23/11/2026
**Base:** V29, preservando temas comemorativos e demais funcionalidades.

## Problema reportado

O operador gerava uma nova revisão a partir de um orçamento de R$ 25.000, alterava o valor para R$ 22.000 e, em alguns casos, não conseguia gravar o novo valor nem emitir o PDF. O contorno era excluir os rascunhos. Essa exclusão não deve ser necessária e pode fazer perder trabalho.

## Alterações

### API / Banco (sem migração)

- Revisões emitidas continuam protegidas; rascunhos são editáveis.
- A chamada de **Nova revisão** encontra e retorna o rascunho existente, caso exista, em vez de gerar erro de conflito.
- O cadastro com rascunho já existente atualiza-o, ao invés de exigir sua exclusão.
- Os itens passam a ser atualizados nas linhas existentes, preservando seus vínculos e sem recriar registros desnecessariamente.
- Criado o endpoint `POST /laboratory/quotes/{id}/emit`: retorna o PDF somente após executar a geração e confirmar a emissão com sucesso. O endpoint GET anterior foi preservado para compatibilidade.
- Fotografias continuam limitadas a **10 por revisão** e preservadas ao editar valores.

### Tela de orçamento

- **Salvar rascunho:** grava os valores e consulta a revisão novamente para verificar se o total recebido coincide com o que estava na tela.
- **Salvar e emitir PDF:** salva alterações pendentes, verifica o valor persistido e só então solicita a emissão.
- A tentativa de emissão com falha apresenta o erro no formulário da OS. Não há aviso de sucesso baseado somente na abertura de nova aba.
- O estado emitido é atualizado após a resposta do servidor; falhas não apagam rascunhos.
- Com rascunho existente, o editor o abre preferencialmente.

## Teste obrigatório no Docker

1. Faça **backup do banco e dos uploads**, e utilize uma OS de homologação.
2. Crie um orçamento de **R$ 25.000,00** e emita a revisão R01.
3. Selecione **Nova revisão**. A revisão R02 inicia com o valor copiado.
4. Em **Serviços e componentes**, altere o **valor unitário** para **R$ 22.000,00** (com quantidade 1).
5. Clique em **Salvar rascunho**. Confirme a mensagem de revisão gravada e total R$ 22.000,00.
6. Saia da OS e abra-a novamente. A R02 deve continuar em rascunho com R$ 22.000,00.
7. Clique em **Salvar e emitir PDF**, abra o PDF e confira o total de R$ 22.000,00.
8. Reabra a R01: ela deve permanecer emitida e manter os R$ 25.000,00.
9. Repita com fotos anexadas e legendadas (inclusive 10 fotos).
10. Tente solicitar uma nova revisão quando já houver um rascunho: a interface deverá reaproveitar o rascunho existente sem exigir exclusão.

**Observação:** o total do orçamento técnico é calculado a partir dos itens e do desconto na aba **Orçamento**. Ele não é automaticamente alterado ao modificar o campo financeiro **Valor orçado** da OS em outra aba. Para mudar o total exibido no PDF, ajuste os itens desta revisão.

## Arquivos principais modificados

- `codigo-fonte/apps/api/app/laboratory/router.py`
- `codigo-fonte/apps/api/app/laboratory/quote_items.py` (novo)
- `codigo-fonte/apps/web/src/features/laboratory/components/QuoteEditor.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `codigo-fonte/apps/api/tests/test_quote_revision_value_recovery_v30.py` (novo)

## Compatibilidade e riscos

- Não houve migração de banco, alteração de nome de projeto Docker ou mudança de volumes.
- Nenhum orçamento emitido foi reescrito. Não foram apagadas fotos ou revisões.
- O instalador continua sendo `INICIAR_SENTICO.cmd` na raiz do ZIP.
- **Validação ainda necessária:** build integral React/Vite e execução real contra PostgreSQL/Docker, incluindo usuário autorizado, PDF em navegador e regressão mobile. Os testes dirigidos em SQLite não substituem essa homologação.
