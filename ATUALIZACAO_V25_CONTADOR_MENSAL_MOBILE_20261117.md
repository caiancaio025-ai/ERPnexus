# SÊNTICO V25 — Ajuste do contador mensal no painel mobile

## Objetivo
Corrigir a apresentação do número total no card **Equipamentos com entrada em [mês]** quando o painel for visualizado no celular.

## Problema corrigido
Em telas pequenas, o número total podia ser quebrado e aparecer “na vertical”, prejudicando a leitura.

## Solução aplicada
- contador com `white-space: nowrap`;
- bloqueio de `overflow-wrap` e `word-break`;
- largura mínima para o número;
- uso de números tabulares;
- distribuição do card em duas colunas no mobile, mantendo texto à esquerda e total à direita.

## Arquivo alterado
- `codigo-fonte/apps/web/src/features/dashboard/dashboard.css`

## Banco / infraestrutura
- sem migração de banco;
- sem alteração de volumes;
- sem alteração do instalador único.

## Como validar
1. Extraia o pacote.
2. Execute `INICIAR_SENTICO.cmd`.
3. Abra o painel inicial no celular ou em modo responsivo.
4. Verifique o card **Equipamentos com entrada em [mês]**.
5. Confirme que o total aparece horizontalmente à direita do card.
