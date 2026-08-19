# Primeiro administrador

1. Instale e inicie o PostgreSQL.
2. Na raiz do projeto, ajuste `.env` para usar o banco local:

```env
DATABASE_URL=postgresql+psycopg://nexus:SUA_SENHA@localhost:5432/nexus
```

3. Instale as dependências de autenticação:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".\apps\api[dev,auth,ai]"
```

4. Execute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\create-admin.ps1
```

O comando cria a tabela `users`, solicita nome, e-mail, usuário e senha, e grava o primeiro usuário com o perfil `super_admin`.
