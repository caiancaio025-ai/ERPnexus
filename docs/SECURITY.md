# Segurança do NEXUS

Nenhum sistema conectado à internet pode prometer risco zero. O objetivo é reduzir a superfície de ataque, limitar danos e recuperar o serviço com rapidez.

## Antes da produção

1. Use uma VPS atualizada, usuário administrativo sem login direto como root e acesso SSH apenas por chave.
2. Desative autenticação SSH por senha e login remoto de root somente depois de validar uma segunda sessão com a chave.
3. Libere no firewall apenas SSH, HTTP e HTTPS. Restrinja SSH ao IP administrativo quando houver IP fixo.
4. Não exponha PostgreSQL, API, Docker socket, painéis de administração ou portas de desenvolvimento.
5. Coloque o domínio atrás de proteção de borda com mitigação DDoS, WAF e rate limit. Proteja especialmente login, recuperação e formulários públicos.
6. Use TLS, headers de segurança, cookies `HttpOnly`, `Secure` e `SameSite`, proteção CSRF e sessão curta.
7. Use Argon2id para senha, atraso progressivo no login, MFA obrigatório para administradores e auditoria de alterações de perfil.
8. Aplique RBAC por recurso, ação, empresa e unidade. A conta nasce sem privilégios.
9. Valide upload por extensão permitida, MIME real, assinatura do arquivo, tamanho, checksum e nome gerado pelo servidor. Armazene fora da pasta pública.
10. Limite corpo da requisição, paginação, tempo de consulta, geração de PDF, concorrência e chamadas Gemini.
11. Mantenha segredos apenas na VPS ou em um cofre. Nunca envie `.env`, chave Gemini ou dump para Git.
12. Faça backup criptografado do PostgreSQL e dos anexos para destino externo. Teste restauração todo mês.

## Proteção contra derrubada do servidor

A VPS não deve receber tráfego volumétrico diretamente. Use uma camada externa anti-DDoS e regras de rate limit. No servidor, aplique limites de CPU e memória aos containers, limite uploads, configure timeouts, monitore disco e reinicie serviços com health checks.

O Caddy desta estrutura limita requisições a 25 MB e adiciona headers. O limite final de cada tipo de arquivo deve ser menor e validado novamente na API.

## Regras mínimas da aplicação

- autenticação e autorização sempre no backend;
- token de sessão fora de `localStorage`;
- queries parametrizadas pelo SQLAlchemy;
- logs sem senha, token, chave, documento integral ou conteúdo sensível desnecessário;
- Gemini sem acesso a SQL, credenciais ou endpoints administrativos;
- ações críticas bloqueadas para a IA;
- dependências atualizadas e auditadas no CI;
- imagem Docker sem root, filesystem somente leitura e capacidades removidas quando possível.

## Monitoramento e resposta

Configure alertas para erro 5xx, uso anormal de CPU, memória e disco, falha de backup, tentativas de login, bloqueios, aumento de custo Gemini e indisponibilidade dos health checks. Documente como revogar chaves, bloquear usuários, restaurar backup e voltar a versão anterior.
