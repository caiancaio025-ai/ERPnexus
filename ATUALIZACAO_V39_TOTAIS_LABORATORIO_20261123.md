# SÊNTICO V39 — Totais monetários do Laboratório na horizontal

## Correção
Os indicadores **Total aprovado** e **Aguardando aprovação**, no cabeçalho do módulo Laboratório, podiam quebrar a moeda e os dígitos em linhas verticais quando o valor aumentava. O problema era uma combinação de cartões estreitos e regra CSS de quebra de texto.

## Alterações aplicadas
- Os dois cartões monetários agora ocupam o equivalente a duas colunas nos monitores maiores.
- A descrição fica acima do valor, reservando uma linha inteira para a quantia.
- O valor usa `white-space: nowrap`, sem quebra de moeda ou centavos.
- Para valores excepcionalmente extensos, há rolagem **dentro do próprio número**, nunca do painel inteiro.
- No celular, os cartões monetários ocupam toda a largura disponível e mantêm o valor horizontal.
- Os demais indicadores, a lógica de cálculo e as regras de acesso permanecem intactos.

## Como testar
1. Faça backup antes de atualizar dados reais; extraia o pacote em uma pasta nova.
2. Abra o Docker Desktop e execute `INICIAR_SENTICO.cmd`.
3. Vá em **Laboratório**. Verifique os cartões **Total aprovado** e **Aguardando aprovação** com valores de R$ 0,00, R$ 47.071,43 e R$ 1.234.567,89.
4. Confira também em largura de celular. Os valores devem permanecer na horizontal.

## Arquivos alterados
- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `testes_instalador/test_v39_totais_laboratorio_horizontal.py`

## Banco e produção
Não há migração adicional, mudança de API, banco, volumes ou instalador. Mantém-se a migração necessária da V36 para os campos de chaves NF, caso ainda não tenha sido aplicada. Nenhuma alteração foi feita à VPS.

## Validação executada
- Teste visual isolado em Chromium nas larguras 320, 390, 768, 1040 e 1440 px, sem quebra dos valores ou rolagem horizontal da página.
- Sintaxe TSX e CSS verificada.
- Testes automatizados do instalador selecionados. O build integrado e a homologação no Docker devem ser executados na máquina de destino antes da produção.
