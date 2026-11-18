# SÊNTICO V17 — correção de orçamentos com fotos

**Base:** SÊNTICO V16 entregue em 16/11/2026. **Data da correção:** 17/11/2026.
**Escopo:** orçamento do Laboratório, anexos de fotografia e geração de PDF. A funcionalidade de estoque, o mobile, as notificações e o instalador da V16 foram mantidos.

## O problema encontrado

Na atualização de um rascunho, o servidor recriava todas as linhas de `laboratory_quote_photos` ao salvar **qualquer informação**, mesmo quando nenhuma fotografia tinha mudado. A tabela possui o índice único `uq_lab_quote_photo_document`; dependendo da ordem do `INSERT` e do `DELETE` executados pelo SQLAlchemy, a gravação falhava por conflito de unicidade. Com isso, a tela parecia não aceitar mudanças de preço ou de texto após anexar fotos.

Também havia um risco independente na emissão: o backend registrava o orçamento como `emitted` **antes** de concluir a geração do PDF. Uma falha de processamento de imagem podia manter uma revisão emitida, apesar de o PDF não ter sido entregue.

## Correções implementadas

1. Na edição de orçamentos, a API **preserva os registros de fotos existentes**, atualizando ordem e legenda quando necessário. Só cria vínculos novos para fotos novas; remove somente os vínculos explicitamente excluídos. Valores, condições e textos continuam sendo gravados na mesma transação.
2. O limite de fotos da revisão passa a **10**, com validação no frontend e na API; fotos duplicadas dentro da mesma revisão são rejeitadas com erro de validação em vez de provocarem erro do banco.
3. O envio de anexos informa os limites de 15 MB por arquivo e formatos JPG, PNG e WEBP. Uma falha em um lote não esconde as imagens que já foram enviadas à tela.
4. Os botões agora mostram erros de salvamento; a tela sinaliza **alterações não salvas**. Visualizar/emitir PDF é bloqueado na interface enquanto existirem alterações pendentes, evitando enviar valores desatualizados.
5. A geração do PDF acontece **antes da confirmação de emissão no banco**. Se o PDF falhar, o orçamento permanece editável; se for concluído, a emissão e o substatus são gravados.
6. Fotos e legendas são agrupadas na paginação do PDF para evitar que uma legenda fique isolada numa página e sua imagem apareça na seguinte. Teste com 10 fotos gerou 7 páginas, sem fotos faltando.

## Como instalar e homologar localmente

1. Faça um **backup do banco PostgreSQL e do volume de uploads** do ambiente com dados reais.
2. Extraia o ZIP **inteiro** em uma pasta própria no Windows; abra o **Docker Desktop** (containers Linux).
3. Execute **`INICIAR_SENTICO.cmd`**, o mesmo instalador único da V16. Aguarde `SENTICO_INICIADO=OK` e abra **http://127.0.0.1:5184/**.
4. Em **Laboratório → O.S. de teste → Orçamento**, selecione um rascunho; registre o preço e salve.
5. Anexe uma foto, clique **Salvar rascunho**, altere o preço, salve novamente, feche e reabra a O.S. Verifique que o valor e a fotografia continuam corretos.
6. Acrescente até 10 imagens, edite legendas e valores, salve, reabra e **Visualize o PDF**. Confira as 10 imagens, número, legenda e valor na proposta.
7. Teste retirar uma foto e adicionar outra, salvar e reabrir. Confirme que nenhuma outra imagem foi perdida.
8. Faça uma emissão real **apenas na O.S. de teste**, depois de salvar. Confirme o substatus e a revisão emitida. Repetir numa cópia isolada do banco evita consequências comerciais.

Se uma revisão histórica **já estiver como emitida**, o sistema continua a protegê-la contra alterações, conforme a regra de histórico. Nesse caso, use **Nova revisão**. Esta correção não desbloqueia automaticamente documentos já emitidos.

**Proteção de dados:** nenhuma nova migração Alembic, exclusão de fotos, modificação de IDs, troca de volumes ou mudança no projeto Docker. Não use `docker compose down -v` nem remova volumes.

## Validação executada nesta entrega

- Teste de persistência com a restrição única em SQLite: valor atualizado com foto existente; ampliação de 1 para 10 fotos; edição de legendas; remoção seletiva; reabertura, tudo aprovado.
- Teste de PDF com 10 fotografias e legendas em orientações vertical/horizontal: aprovado, inclusive inspeção visual das páginas geradas.
- Testes direcionados de laboratório e PDF: **46 aprovados**.
- Sintaxe Python e TSX validada.
- **Limitações:** a suíte geral possui outros testes que dependem de arquivos antigos ausentes do ZIP e do driver `psycopg` não instalado neste ambiente; a compilação integral do frontend não foi concluída por falta do pacote NPM `vite` em cache. Não foi possível testar Docker/PostgreSQL/Windows com dados reais aqui. A homologação local é obrigatória antes da VPS.
