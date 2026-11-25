# SÊNTICO V41 — Correção do salvamento de orçamentos

## Problema relatado
Na V40, ao clicar em salvar um orçamento em rascunho, o formulário podia piscar e voltar ao valor anterior (por exemplo, R$ 25.000,00 após uma edição para R$ 22.000,00).

## Causas e correções no código

1. **Reidratação prematura do formulário:** `persistDraft()` chamava `load()` e atualizava o formulário antes de conferir os valores persistidos. Agora a API retorna primeiro a revisão salva; o cliente verifica a resposta e a reconsulta ao servidor antes de atualizar a interface. Falhas preservam as edições na tela e geram um erro explícito.
2. **Botão geral separado do orçamento:** `Salvar alterações` no rodapé da OS executava somente o salvamento dos dados gerais da OS. Agora, na aba **Orçamento**, o botão é **Salvar orçamento** e aciona o mesmo salvamento da proposta.
3. **Entrada de valores:** o campo de valor unitário passa a aceitar números com vírgula brasileira e separador de milhar (por exemplo `22.000,00` ou `25.000`). Quantidades continuam tratadas como valores decimais, para preservar entradas como `1.000` = 1 unidade. As quantias são normalizadas antes de enviar à API.
4. **Leituras assíncronas:** respostas antigas da lista de revisões não substituem valores que começaram a ser digitados enquanto a tela carregava.
5. **Feedback:** avisos de sucesso/falha ficam visíveis no topo da aba, e a confirmação cobre itens, subtotais, total, desconto, textos e fotos.

## Arquivos alterados

- `codigo-fonte/apps/web/src/features/laboratory/components/QuoteEditor.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/components/quoteSaveGuard.ts` (novo)
- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/api/tests/test_quote_revision_value_recovery_v30.py` (atualização da regressão)
- `codigo-fonte/apps/web/tests/test_quote_save_guard_v41.cjs` (novo)

## Homologação recomendada

1. Faça backup do PostgreSQL e dos arquivos de uploads.
2. Extraia em nova pasta; execute `INICIAR_SENTICO.cmd` com o Docker Desktop aberto.
3. Abra uma OS com orçamento **emitido** de R$ 25.000,00 e crie ou retome uma revisão em **rascunho**.
4. Modifique o valor unitário para que o orçamento some **R$ 22.000,00**.
5. Clique **Salvar rascunho** dentro do orçamento. Confira a confirmação no topo e reabra a OS: o valor deve permanecer R$ 22.000,00.
6. Repita a alteração usando o botão **Salvar orçamento** no rodapé externo da OS. Verifique que ele salva os mesmos itens.
7. Confirme que o PDF usa a revisão correta; que a revisão emitida anterior mantém seus valores; e que as fotos permanecem anexadas.
8. Se houver erro, observe a mensagem no topo da aba e os logs da API. **Não exclua rascunhos para tentar forçar uma nova gravação.**

Observação: a aba **Valores** da OS tem seus próprios campos financeiros. Ela não modifica automaticamente os valores unitários dos itens do orçamento.

## Compatibilidade e validação

- **Sem nova migração de banco**, sem alterações nos volumes ou na VPS. A migração introduzida na V36 continua necessária para ambientes que ainda não a aplicaram.
- **72 testes aprovados**, **1 teste de integração não executado** por ausência de dependência PostgreSQL, e **20 verificações da proteção contra perda de valores**.
- Arquivos TypeScript alterados passaram nas verificações sintáticas; a compilação React/Vite completa e a homologação Docker não puderam ser realizadas neste ambiente.

Esta atualização foi preparada para testes locais antes de subir à produção.
