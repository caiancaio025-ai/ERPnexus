# SÊNTICO V38 — Texto de orientação da pesquisa de clientes

## Alteração
O texto **“Digite parte do nome e escolha uma sugestão.”** foi movido para a mesma faixa horizontal do rótulo **“Cliente *”**, alinhado à direita. A caixa de pesquisa permanece logo abaixo, sem texto adicional ocupando outra linha.

Aplica-se tanto à inclusão de uma nova OS quanto à edição de uma OS existente. Em telas pequenas, o texto de ajuda pode ocupar duas linhas **dentro da área à direita do rótulo**, sem sobrepor o campo.

## Arquivos alterados
- `codigo-fonte/apps/web/src/features/laboratory/components/CustomerSearchSelect.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `codigo-fonte/apps/web/src/shared/theme/light-theme.css`

## Como validar
1. Abra o Docker Desktop e execute `INICIAR_SENTICO.cmd`.
2. Acesse Laboratório → Nova OS, depois a tela Edição completa de uma OS.
3. Observe que o texto aparece ao lado de **Cliente** e não abaixo do campo.
4. Teste em mobile e nos temas claro/escuro.

Sem migração de banco ou alterações de volumes.
