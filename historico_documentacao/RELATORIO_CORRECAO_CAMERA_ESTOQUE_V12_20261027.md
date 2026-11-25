# SÊNTICO ERP — V12 — Câmera direta no Estoque

**Base:** `SENTICO_GREEN_V11_NF_NORMAIS_E_GARANTIA_COMPLETO_20261027.zip`.

## Problema confirmado

O Estoque usava `input type="file" capture="environment"` com o rótulo «Abrir câmera do dispositivo». O atributo `capture` apenas sugere ao navegador usar a câmera, mas pode abrir o seletor de arquivos. Não fornece visualização ao vivo ou captura garantida em desktop.

## Correções

- Ação explícita **Tirar foto com a câmera** no formulário de cadastro/edição de itens.
- Ação **Tirar foto com a câmera** também nos detalhes de itens existentes.
- Usa `CameraCapture` existente do Laboratório, com `navigator.mediaDevices.getUserMedia`, prévia de vídeo, botão **Capturar foto**, permissão do navegador e encerramento das trilhas após a captura/fechamento.
- O cadastro/edição mantém a foto capturada em `pendingPhoto` e envia pelo endpoint anterior `/inventory/items/{id}/photos` ao salvar. Os detalhes enviam a foto imediatamente pelo mesmo endpoint.
- **Escolher foto do dispositivo** permanece como ação independente, sem atributo `capture` forçando comportamento inesperado. O botão alternativo dentro do componente da câmera também abre exclusivamente a escolha de arquivo.
- O estado de envio de foto é limpo mesmo quando ocorre falha na requisição.
- O layout de ações foi ajustado ao tema azul do Estoque e a telas estreitas.

## Arquivos modificados

1. `codigo-fonte/apps/web/src/features/inventory/InventoryDashboard.tsx`
2. `codigo-fonte/apps/web/src/features/inventory/inventory.css`
3. `codigo-fonte/apps/web/src/features/laboratory/components/CameraCapture.tsx`

Sem alterações de API, PostgreSQL, Alembic, Docker ou volumes. As demais funcionalidades da V11 permanecem intactas.

## Validações executadas neste ambiente

- Parser TypeScript/TSX: zero erros de sintaxe nos dois arquivos TSX afetados.
- Verificações estáticas de contrato: comando separado para abrir câmera, ausência de `capture` no seletor, utilização de `getUserMedia`, cadastro salva foto capturada e detalhes enviam foto capturada.
- Comparação com ZIP V11: apenas os três arquivos acima mudaram no código.
- Integridade CRC de ambos os ZIPs e manifesto SHA-256 do pacote completo.

## Homologação pendente (Windows / navegador)

1. Abra Docker Desktop e entre na V12 local.
2. Em Estoque → Novo item, clique **Tirar foto com a câmera**, autorize, confira a prévia, capture e salve.
3. Reabra o item: a foto deve estar nos detalhes.
4. Em um item existente, clique **Tirar foto com a câmera**, capture e confirme que a foto foi anexada sem trocar o cadastro.
5. Confira a alternativa **Escolher foto do dispositivo**.
6. Confira se a câmera desliga ao fechar a janela de captura.
7. Confira se a câmera continua funcionando no Laboratório.

**Nota:** `getUserMedia` exige origem segura no navegador (HTTPS ou localhost/127.0.0.1). Em um celular que acesse o computador pelo IP local via HTTP, o navegador pode impedir o acesso direto à câmera. Essa condição não pode ser resolvida apenas com o frontend; é necessária uma origem segura HTTPS ou utilizar o seletor de foto como alternativa.

**Não validado aqui:** build completo da Web (dependências npm indisponíveis nesta execução), testes de navegador/câmera real e testes com Docker/PostgreSQL.
