# SÊNTICO V28 — Calendário dos temas comemorativos

## Objetivo
Ajustar o comportamento automático dos temas comemorativos conforme solicitado:
- **Natal em novembro e dezembro**;
- **Ano-Novo em janeiro**, com fogos de artifício.

## Alterações realizadas

### 1) Calendário automático
- Janeiro: **Ano-Novo**
- Fevereiro: **Carnaval**
- Março ou abril: **Páscoa** (conforme o ano)
- Junho: **São João**
- Outubro: **Halloween**
- Novembro e dezembro: **Natal**

### 2) Seletor manual
A opção **Ano-Novo** foi incluída na seleção manual de prévia dos temas comemorativos.

### 3) Decoração do Ano-Novo
Foi adicionada uma decoração visual de **fogos de artifício**, respeitando as opções do usuário para ativar ou desativar as animações.

## Arquivos alterados
- `codigo-fonte/apps/web/src/shared/theme/seasonal.ts`
- `codigo-fonte/apps/web/src/shared/theme/SeasonalDecorations.tsx`
- `codigo-fonte/apps/web/src/shared/theme/seasonal.css`
- `LEIA_PRIMEIRO_SENTICO.md`

## Banco / infraestrutura
- sem migração de banco;
- sem alteração de volumes Docker;
- sem alteração no instalador único.

## Como validar
1. Extraia o pacote e execute `INICIAR_SENTICO.cmd`.
2. Acesse **Aparência → Temas comemorativos**.
3. Selecione **Ano-Novo** para testar a prévia.
4. Confirme que, no modo automático, novembro e dezembro usam **Natal** e janeiro usa **Ano-Novo**.
