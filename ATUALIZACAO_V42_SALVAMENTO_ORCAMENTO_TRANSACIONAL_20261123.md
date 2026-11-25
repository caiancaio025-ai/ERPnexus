# SÊNTICO V42 — Salvamento de orçamento com confirmação transacional

## Falha relatada

Na OS 30740, ao tentar alterar o valor de uma revisão R02 em rascunho, a V41 mostrou “O total retornado pelo servidor está diferente do valor informado” e impediu a conclusão do salvamento. A V41 parava na primeira resposta de atualização sem conferir o registro novamente após o commit. **Sem acesso ao banco real do usuário, não foi possível determinar se o registro foi ou não gravado nessa tentativa específica.**

## Correções desta versão

1. **Validação do contrato da API antes de salvar:** a interface consulta `/api/laboratory/quotes/write-contract` e exige `quote-save-v42`. Caso o frontend esteja atualizado e a API ainda rode uma imagem anterior, o sistema informa que é preciso atualizar/reiniciar o container API, em vez de apresentar apenas uma divergência de valor.
2. **Gravação transacional no backend:** o endpoint de orçamento atualiza os itens e totais, executa `flush`, consulta por SQL os valores e itens realmente armazenados na transação e só então confirma o commit. Se ocorrer divergência, a operação não é confirmada.
3. **Precisão monetária explícita:** as colunas NUMERIC são gravadas com duas casas decimais; quantidade com até três casas. O total é calculado com `Decimal` e arredondamento definido para centavos.
4. **Confirmação após a atualização:** o frontend verifica a revisão em uma nova consulta sem cache **antes de substituir os valores digitados**. Um retorno inicial divergente não bloqueia sozinho o salvamento se a leitura confirmada estiver correta.
5. **Erros úteis:** divergências passam a informar o total solicitado e o registrado, incluindo o número da revisão. A interface nunca apaga os dados em edição por uma confirmação malsucedida.
6. **Histórico preservado:** revisões emitidas permanecem imutáveis; rascunhos não precisam ser excluídos para salvar novamente. Os vínculos de fotografias e legendas continuam no mesmo fluxo.

## Como atualizar localmente

1. Faça backup do PostgreSQL e dos uploads antes de executar o instalador.
2. Extraia **todo o ZIP da V42 em uma pasta nova**.
3. Abra o Docker Desktop e execute **`INICIAR_SENTICO.cmd`**. Aguarde a confirmação de inicialização. O instalador recompila **API e WEB** e recria o container API para evitar versões desencontradas.
4. Abra a aplicação e faça uma atualização forçada do navegador (`Ctrl+Shift+R`).
5. Abra a **OS 30740**, selecione o **rascunho R02** (não a R01 emitida), altere um valor unitário, confira a coluna “Total do item” e clique **Salvar orçamento**.
6. Feche e reabra a OS, confirme o valor no rascunho e só depois use **Salvar e emitir PDF**.
7. **Não apague rascunhos** e não utilize `docker compose down -v` nem apague volumes.

## Quando um erro persistir

- **“API de orçamentos desatualizada”**: a interface V42 está comunicando com um servidor de versão anterior. Confirme que o instalador V42 recompilou e recriou o container API correto.
- **“Divergência no total: solicitado ... registrado ...”**: anote o valor solicitado e o registrado e confira se outra sessão está editando a mesma revisão. Não exclua a revisão.
- **Mensagem HTTP 409 de conferência no banco:** a transação não foi confirmada; procure o erro correspondente nos logs do container API da instalação de homologação. Não compartilhe credenciais, tokens ou cópias integrais do banco.

## Arquivos modificados

- `codigo-fonte/apps/api/app/laboratory/router.py`
- `codigo-fonte/apps/api/app/laboratory/schemas.py`
- `codigo-fonte/apps/web/src/features/laboratory/components/QuoteEditor.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/components/quoteSaveGuard.ts`
- testes `test_quote_save_v42.py` e `quote-save-v42.test.mjs`; ajustes de expectativas de testes antigos sem alterar regras de negócio

## Validação e limitações

- Teste de atualização R02 de R$ 8.500 para R$ 22.000, consultas posteriores, alteração de quantidade/preço e preservação de R01 emitida em banco SQLite descartável.
- Testes das rotinas de valores, revisão e fotografias de orçamento.
- Verificação sintática dos arquivos TypeScript/TSX e Python modificados.
- Testes do instalador único e de compatibilidade.
- **Pendente:** build integral React/Vite e homologação real PostgreSQL/Docker com a OS 30740. O banco de produção e a VPS não foram alterados.

**Banco:** nenhuma nova migração Alembic; mantém a revisão existente `20261123_01`.
