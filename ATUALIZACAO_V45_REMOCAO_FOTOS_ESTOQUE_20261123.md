# SÊNTICO V45 — Remover foto de item do Estoque

## O que foi implementado

- Em **Estoque → Detalhes do item**, cada foto anexada agora tem o botão **Remover foto**, acompanhado de confirmação.
- É possível remover uma foto errada e anexar outra, sem excluir ou recadastrar o item.
- Ao confirmar, a API remove o registro daquela foto do item, confirma a gravação e então limpa o arquivo armazenado. Nenhuma outra foto é excluída.
- A lista de itens e a janela de detalhes atualizam suas imagens quando o servidor confirma a operação.
- Se houver falha, o sistema mostra uma mensagem no próprio detalhe e preserva as imagens não removidas.
- Também foi criado o botão **Descartar foto selecionada** no cadastro/edição, para cancelar um arquivo ainda não enviado.

## Segurança

- O endpoint `DELETE /inventory/items/{item_id}/photos/{photo_id}` exige permissão para **Estoque**.
- Uma foto só pode ser excluída quando estiver vinculada ao item especificado; caso contrário, o servidor retorna 404.
- A exclusão não altera o saldo, localização, código, histórico ou preços do item.
- Nenhuma migração de banco é necessária.

## Arquivos alterados

- `codigo-fonte/apps/api/app/inventory/router.py`
- `codigo-fonte/apps/web/src/features/inventory/InventoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/inventory/inventory.css`
- `testes_instalador/test_v45_remover_fotos_estoque.py`
- `LEIA_PRIMEIRO_SENTICO.md`

## Testes locais efetuados

- 6 testes dirigidos de exclusão de fotos (incluídos na suíte de 57 testes do instalador/pacote) aprovados.
- Verificação de sintaxe TSX aprovada.
- Compilação Python do router aprovada.
- Compilação completa React/Vite e homologação real no Docker/PostgreSQL continuam necessárias antes da implantação na VPS.

## Roteiro rápido de homologação

1. Faça backup do PostgreSQL e dos uploads existentes.
2. Extraia o ZIP completo em pasta nova e execute `INICIAR_SENTICO.cmd` com Docker Desktop aberto.
3. Em **Estoque**, abra um item que tenha duas ou mais fotos.
4. Clique em **Remover foto** na foto incorreta, confirme e verifique que apenas ela desapareceu.
5. Feche, reabra o item e atualize a página para confirmar que a remoção persistiu.
6. Anexe uma foto correta e confira a miniatura atualizada na listagem.
7. No cadastro/edição, selecione um arquivo e clique em **Descartar foto selecionada** antes de salvar; ele não deve ser anexado.
8. Confira tanto o tema claro quanto o escuro e a visualização pelo celular.

**A VPS não foi alterada.**
