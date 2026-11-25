# SÊNTICO V14 — Ajuste de cadastro inicial no instalador

Esta atualização modifica **somente** o instalador `INSTALAR_SENTICO_DEV.ps1` da V14.

## Comportamento

1. Confere a identidade do projeto Docker e o PostgreSQL antes de consultar usuários.
2. Após preparar a revisão inicial do banco, lê `SELECT COUNT(*) FROM users`.
3. **Se houver um ou mais usuários:** não executa `app.dev_seed_admin`, não altera login, senha, papel ou módulos de ninguém, informa `CADASTRO_ADM_TESTE_IGNORADO=OK` e segue para `alembic upgrade head`.
4. **Se houver zero usuários:** executa o cadastro fictício inicial no ambiente de desenvolvimento local; confere sua existência e segue para as migrations.
5. Em banco existente, não anuncia `adm/123` como credencial válida: manda utilizar conta já cadastrada.
6. Se a consulta SQL falhar, o instalador interrompe a execução; **não** assume que a base está vazia.

## Instalação

- Copie `INSTALAR_SENTICO_DEV.ps1` para a **raiz da pasta V14**, ao lado de `INICIAR_SENTICO_GREEN.cmd`, substituindo somente o instalador antigo.
- Preserve `codigo-fonte/.env.dev`, os volumes Docker e os demais arquivos da aplicação.
- Abra Docker Desktop e execute `INICIAR_SENTICO_GREEN.cmd` como antes.

## Limites e cuidados

- O instalador é destinado **somente ao Docker Desktop local de desenvolvimento**, não à VPS.
- Não houve mudança de migration, código do frontend ou API. A revisão esperada segue `20261028_01`.
- A etapa 06 original pode **sincronizar a senha da role PostgreSQL** caso a senha do `.env.dev` esteja diferente da role dentro do volume. Isso é diferente das contas de usuários do ERP, que não são modificadas por esta atualização.
- Um banco existente pode ter contas sem acesso ou desativadas; conforme solicitado, a presença de **qualquer usuário** impede a criação automática de `adm`. O instalador não recupera senhas de contas já existentes.
- A versão foi inspecionada e validada por testes estáticos nesta sessão. Não foi executada em Docker Desktop/PowerShell Windows.
- **Nunca** use `docker compose down -v` para atualizar.
