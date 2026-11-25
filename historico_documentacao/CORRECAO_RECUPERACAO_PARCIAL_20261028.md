# Recuperação parcial — procedimento atual

Se o volume isolado `sentico-v14-recuperado_pgdata` já existe, ele é reutilizado, nunca sobrescrito automaticamente. O instalador verifica estrutura, revision e totais, testa autenticação TCP e, somente se necessário, recupera a senha técnica com o banco **isolado e parado** usando o modo stand-alone.

A recuperação não toca em `sentico-dev-entrega_dev_postgres_data` nem redefine senhas de usuários SÊNTICO. Para o roteiro completo, leia `LEIA_PRIMEIRO_RECUPERACAO_V14.md`.
