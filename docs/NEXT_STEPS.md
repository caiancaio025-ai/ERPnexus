# Próximos passos de implementação

## Fase 1 — fundação

- validar execução em duas máquinas;
- criar primeira migration;
- configurar CI no repositório;
- definir domínio, DNS e ambiente de homologação;
- registrar decisões de arquitetura.

## Fase 2 — identidade

- tabela de usuários, convites, sessões, perfis e permissões;
- Argon2id, cookie seguro, CSRF e recuperação de acesso;
- login e cadastro pendente ligados à API;
- aprovação administrativa e auditoria;
- testes de brute force, isolamento por empresa e acesso mínimo.

## Regra de código

Não criar serviço, helper, interface ou dependência sem um caso de uso atual. Arquivo acima de 300 linhas entra em revisão. Comentário deve explicar decisão ou risco, não repetir a sintaxe.
