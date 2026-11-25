# SÊNTICO V32 — Substituição da logo do orçamento

## Objetivo
Substituir a logomarca antiga usada nos **orçamentos do Laboratório** pela nova imagem enviada pelo usuário.

## Alteração realizada
A nova logo foi aplicada em dois pontos do PDF de orçamento:

1. **Cabeçalho do orçamento**
2. **Marca d’água do documento**

Para melhor resultado visual, a imagem enviada foi tratada com **remoção do fundo preto** e exportada com **transparência**.

## Arquivos alterados
- `codigo-fonte/apps/api/app/laboratory/assets/gear_logo.png`
- `codigo-fonte/apps/api/app/laboratory/assets/gear_watermark.png`
- `LEIA_PRIMEIRO_SENTICO.md`

## Banco / infraestrutura
- sem migração de banco;
- sem alteração de volumes Docker;
- sem alteração no instalador único;
- sem mudança nas regras dos orçamentos.

## Como validar
1. Extraia o pacote e execute `INICIAR_SENTICO.cmd`.
2. Abra uma O.S. no Laboratório.
3. Gere ou reemita um orçamento em PDF.
4. Verifique se a nova logomarca aparece no cabeçalho e na marca d’água.

## Observação
Esta versão é apenas visual e não altera o comportamento do orçamento.
