# SÊNTICO V14 — Diagnóstico da role PostgreSQL ausente

## Causa comprovada pelo log

O PostgreSQL responde pelo socket, mas a role `sentico_dev` não está presente. A falha ocorre antes do teste `SELECT COUNT(*) FROM users`; não é um problema de falta de usuários do ERP.

O Compose pede POSTGRES_USER=sentico_dev, mas esse valor só inicializa a role quando o diretório de dados está vazio. Um volume importado/inicializado anteriormente preserva seus próprios roles e bancos.

## Ajuste de segurança

- Antes de construir a aplicação, o instalador inicia exclusivamente o serviço `db` e testa a identidade esperada `sentico_dev` / banco `sentico_dev`.
- Se a role ou banco não corresponde, ele interrompe, orienta executar o diagnóstico e **não cria roles, não altera senhas e não executa migrations**.
- Se `.env.dev` sumiu mas o volume existe, não cria uma senha nova.
- Quando a identidade está correta, executa o restante do instalador, incluindo a regra V14 de ignorar o cadastro inicial se já existem usuários.
- O comando `DIAGNOSTICAR_VOLUME_SENTICO.cmd` faz consultas de leitura, tenta algumas roles locais conhecidas e exibe somente nomes de roles e bancos (sem senhas).

## Instalação

1. Faça uma cópia da pasta do projeto e um backup verificável do PostgreSQL antes de novas tentativas de mudança.
2. Extraia os arquivos do ZIP mínimo na pasta principal V14, ao lado do `INICIAR_SENTICO_GREEN.cmd`, sem substituir `codigo-fonte/.env.dev`.
3. Execute `DIAGNOSTICAR_VOLUME_SENTICO.cmd` e envie a saída; o diagnóstico não exclui nada.
4. Não rode novamente o instalador se o diagnóstico indicar roles/bancos divergentes. Precisamos reconciliar os nomes e a propriedade da base antes de qualquer modificação.

## Limites

A correção entregue aqui **previne comandos perigosos e explica a incompatibilidade**, mas não inventa ou cria automaticamente um usuário PostgreSQL: isso requer identificação e confirmação do volume importado. Não é possível garantir a resolução total do erro sem inspecionar o banco real. O código foi validado estaticamente, sem PowerShell/Docker Desktop Windows.

O instalador original V14 inclui uma rotina de sincronização de senha (`ALTER ROLE`) se a role esperada já existe, apenas se houver divergência confirmada. O pré-teste não altera essa rotina, mas impede a entrada nela quando a role está ausente.
