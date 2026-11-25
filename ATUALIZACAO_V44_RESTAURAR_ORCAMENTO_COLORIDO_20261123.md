# SÊNTICO V44 — Restauração da apresentação colorida do orçamento

## Alteração

A apresentação do PDF foi revertida para a base **V42**, exatamente como estava antes da V43:
- Cabeçalho azul com texto branco e logo colorida;
- Faixas e destaques azuis originais;
- Quadros, tabelas e totais do orçamento na apresentação anterior;
- Marca-d'água original restaurada;
- Paginação, fotos, laudo e condições comerciais preservados.

As alterações de preto e branco implementadas na V43 **não** estão presentes nesta versão.

## Compatibilidade e segurança

- Código da aplicação corresponde ao pacote V42;
- Sem nova migração de banco;
- Sem alterações no instalador, volumes Docker ou banco de dados;
- Correções da V42 para salvar orçamento e revisões permanecem.

## Homologação

Faça backup do PostgreSQL e dos uploads. Execute `INICIAR_SENTICO.cmd` no Windows com Docker Desktop aberto e gere um orçamento de teste para verificar o retorno do layout anterior. Nenhuma alteração foi realizada na VPS.
