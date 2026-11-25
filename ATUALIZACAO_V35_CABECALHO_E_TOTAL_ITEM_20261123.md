# SÊNTICO V35 — Cabeçalho do orçamento e total por item

## Objetivo
Ajustar a leitura do cabeçalho do PDF de orçamento e melhorar a visualização dos valores por item no editor do Laboratório.

## Ajustes realizados

### 1) Cabeçalho do PDF
- reorganização do título **ORÇAMENTO PRÉVIO E ESTIMATIVO** em duas linhas mais equilibradas;
- redistribuição das larguras do cabeçalho;
- manutenção do destaque de **Nº da O.S.**, **Emissão** e **Validade**.

### 2) Editor do orçamento
- inclusão da coluna **Total do item**;
- cálculo automático com base em **quantidade × valor unitário**;
- ajuste das larguras e do layout mobile para a nova coluna.

## Arquivos alterados
- `codigo-fonte/apps/api/app/laboratory/quote_pdf.py`
- `codigo-fonte/apps/web/src/features/laboratory/components/QuoteEditor.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `LEIA_PRIMEIRO_SENTICO.md`

## Banco / infraestrutura
- sem migração de banco;
- sem alteração de volumes Docker;
- sem alteração no instalador único.

## Como validar
1. Extraia o pacote e execute `INICIAR_SENTICO.cmd`.
2. Gere ou reemita um orçamento em PDF no Laboratório e confira o cabeçalho.
3. Abra a aba do orçamento e verifique se a grade mostra: **Descrição / Qtd. / Valor unitário / Total do item**.
4. Teste um item com quantidade 2 e valor unitário 1500 para confirmar o total de **R$ 3.000,00**.
