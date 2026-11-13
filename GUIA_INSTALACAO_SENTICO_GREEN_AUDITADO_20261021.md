> **Instalador atual:** use apenas `INICIAR_SENTICO.cmd` na raiz do pacote. Este documento descreve versões antigas e foi mantido para referência histórica. Veja `LEIA_PRIMEIRO_SENTICO.md`.

> **Atualizacao do kit com instalador (22/10/2026):** use `INICIAR_SENTICO_GREEN.cmd` na raiz do pacote. Ele pre-cadastra automaticamente o usuario **adm**, senha **123**, e-mail ficticio `adm@.com.br` no banco local e conclui migrations. Instrucoes antigas para cadastrar um administrador manualmente aplicam-se somente a instalacao manual sem o instalador. Nao usar essas credenciais em producao.

# SÊNTICO Green — Guia de instalacao integrado (22/10/2026)

**ATENCAO:** nesta versao, o procedimento principal e automatizado.

1. Abra Docker Desktop com Linux Engine.
2. Extraia TODO o ZIP para um diretorio novo.
3. Dê duplo clique em `INICIAR_SENTICO_GREEN.cmd`, na **raiz** do diretorio extraido.
4. Responda ao assistente de criacao do administrador de desenvolvimento.
5. Acesse `http://127.0.0.1:5184/`.

Leia `../LEIA_PRIMEIRO_INSTALACAO.md` para todas as verificacoes, problemas conhecidos e limites.

**Nao copie e cole linhas de instalacao manual em sequencia.** O log de 22/10 mostrou comandos concatenados e uma divergencia de senha entre `.env.dev` e o volume PostgreSQL. O instalador verifica essas condicoes sem apagar dados.

O desenvolvedor pode editar API/Web e executar regressao local. A base de dados e totalmente separada da VPS.
