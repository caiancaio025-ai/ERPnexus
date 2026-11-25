# SÊNTICO V33 — Ajuste da logo do orçamento

## Objetivo
Ajustar a identidade visual dos PDFs de orçamento conforme solicitado:
- **logo nova no cabeçalho**;
- **logo antiga como marca d’água**;
- preservação das **cores originais** da nova logo, com o **preto mantido**.

## Alterações realizadas

### 1) Cabeçalho do orçamento
- a nova logo enviada pelo usuário foi mantida no cabeçalho;
- o tratamento gráfico remove apenas o fundo externo conectado às bordas;
- os elementos pretos internos da logo permanecem pretos.

### 2) Marca d’água
- a marca d’água foi restaurada para a **logo antiga** do sistema.

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
4. Verifique se a nova logomarca aparece no cabeçalho com as cores corretas.
5. Verifique se a marca d’água voltou a usar a logo antiga.
