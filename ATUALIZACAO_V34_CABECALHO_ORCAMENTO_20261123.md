# SÊNTICO V34 — Ajuste do cabeçalho do orçamento

## Objetivo
Melhorar a legibilidade do cabeçalho do PDF de orçamento do Laboratório.

## Ajustes realizados
- redução do tamanho do nome da empresa para evitar corte das linhas inferiores;
- aumento e destaque visual de **CNPJ**, **telefone** e **e-mail**;
- aumento e negrito para **Nº da O.S.**, **Emissão** e **Validade**;
- redistribuição das larguras e altura do cabeçalho para acomodar melhor os textos.

## Arquivo alterado
- `codigo-fonte/apps/api/app/laboratory/quote_pdf.py`
- `LEIA_PRIMEIRO_SENTICO.md`

## Banco / infraestrutura
- sem migração de banco;
- sem alteração de volumes Docker;
- sem alteração no instalador único.

## Como validar
1. Extraia o pacote e execute `INICIAR_SENTICO.cmd`.
2. Gere ou reemita um orçamento em PDF no Laboratório.
3. Verifique o cabeçalho, principalmente:
   - nome da empresa;
   - CNPJ, telefone e e-mail;
   - Nº da O.S., Emissão e Validade.
