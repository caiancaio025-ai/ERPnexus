# SÊNTICO V15 — OS → Receitas e parcelas

Data: 12/11/2026
Base: SENTICO_V15_INSTALADOR_UNICO_ESTOQUE_REDESIGN_20261112.zip

## Alterações

1. Botão de retorno do detalhe da OS para Receitas, sempre usando o ID persistido da OS.
2. Resumo financeiro dentro de Valores: total lançado, recebido, pendente e ainda não lançado.
3. Endpoint protegido `/api/finance/work-orders/{id}/receivables`, com todos os títulos da OS, sem filtro mensal.
4. Em Receitas, visão da OS com acesso a cada parcela, incluindo datas de vencimento e situação da baixa.
5. Cadastro contextual da receita com sugestão de saldo ainda não lançado (evita cadastrar o total novamente quando parte já está registrada).
6. No cadastro Parcelado, divisão explícita dos centavos e sugestão de vencimentos mensais, editáveis individualmente.
7. Estado das baixas e auditoria financeira existentes preservados. Nenhum documento/lançamento antigo é reescrito.

## Conferências

- Testes de saldos com parcelas pendentes/recebidas/canceladas e de excedentes: 2 aprovados.
- Testes de divisão exata (100,00/3; 1000,01/6; 3456,78/12) e datas mensais (inclusive fevereiro bissexto): aprovados.
- Verificação de sintaxe TS/TSX e Python: aprovada.
- Compilação integral e teste integrado no Windows/Docker: não realizados por ausência das dependências locais.

## Instalação segura

Extraia o ZIP e execute exclusivamente `INICIAR_SENTICO.cmd`. Faça backup de volumes/dados e uploads antes de atualizar; **não** use `docker compose down -v` nem `docker volume prune`.
