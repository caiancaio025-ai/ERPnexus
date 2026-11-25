# SÊNTICO V14 — Inicializador por compatibilidade (29/10/2026)

## O que mudou

A V14 passa a identificar a instalação existente **pelos containers do projeto e pelo conteúdo do PostgreSQL**, não por um nome obrigatório de volume, role ou banco.

Ordem de prioridade:

1. Se existem containers do projeto `sentico-v14-recuperado`, reusar os volumes que **eles realmente montam**, mesmo que o nome do volume tenha mudado.
2. Se existe a configuração persistente em `%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao`, reusar as escolhas e a senha já salvas.
3. Usar como padrão os volumes da V14 que já funcionaram: `sentico-v14-recuperado_pgdata`, `sentico-v14-recuperado_uploads`, `sentico-v14-recuperado_node_modules`.
4. Se o volume de PostgreSQL escolhido não existe, procurar **uma única** origem PostgreSQL 17 livre e fazer uma **cópia** para o volume de destino, sem alterar a origem. Não clonar uma origem montada em container de outro projeto.
5. Se não houver essa origem, procurar backups `.tar.gz` nas pastas de importação/backup/Área de Trabalho/Downloads e aceitar um arquivo pela estrutura física PostgreSQL 17, não pelo nome do arquivo.
6. Subir PostgreSQL, detectar a role administrativa caso a configurada não exista, e descobrir bancos com tabelas do SÊNTICO e uma migration Alembic reconhecida. Se o banco anterior ainda for compatível, mantê-lo.
7. Só executar migrations após confirmar autenticação, revisão do banco e escrita pela mesma conexão da API.

**Compatibilidade não significa que qualquer banco PostgreSQL servirá:** versão física 17, tabelas SÊNTICO, role acessível e sequência Alembic compatível continuam obrigatórios para prevenir danos. Não existe conversão automática de PostgreSQL 16 para 17, nem recuperação de backups físicos inconsistentes.

## Instalar ou atualizar

- Primeiro, preserve seu backup externo dos dados existentes.
- Extraia o pacote completo em uma pasta nova ou aplique somente o pacote de correção sobre a pasta V14 atual.
- Mantenha o Docker Desktop aberto e execute `INICIAR_SENTICO_V14.cmd`.
- Em caso de sucesso, acesse http://127.0.0.1:5184/ com uma conta já cadastrada. Não será criado `adm/123`.
- Para informação segura sem credenciais, execute `DIAGNOSTICAR_SENTICO_V14_FIXO.cmd`.

## Seguranças mantidas

- Os volumes em produção, os volumes `sentico-dev-entrega_*` e a VPS não são alterados por esta rotina.
- **Não** executar `docker compose down -v`, `docker volume rm` nem limpar volumes.
- Um volume encontrado fora deste projeto nunca é usado diretamente para escrita; somente uma cópia independente quando há origem unívoca e desocupada.
- Quando existem várias fontes avulsas, a seleção automática é interrompida, em vez de escolher dados errados.
- O instalador **não cria banco de aplicação vazio** para passar na inspeção.
- A role é uma conta do PostgreSQL, diferente dos logins dos usuários do ERP. Detectar role não muda senhas dos usuários do sistema.
- As migrations podem modificar a **cópia V14**; mantenha sempre seu backup anterior.

## Validação e limites

Foram realizados: teste de sintaxe shell, compilação Python, checagem do Compose, contratos de volumes/role/banco, catálogo simulado com nomes novos e revisão do ZIP. **Não foi possível executar Docker Desktop e PowerShell do Windows neste ambiente**; portanto, a instalação real deve ser homologada no notebook antes de considerar a adaptação totalmente concluída.

Não envie arquivos `.env`, senhas, volumes com dados de clientes ou backups para diagnóstico. Compartilhe apenas os marcadores de erro.
