# NEXUS — Etapa 1 de estabilização

## Alterações executadas

- Remoção de `.venv`, `node_modules`, caches Python, `.astro`, builds e arquivos compilados.
- Remoção do `.env` real do pacote e criação de `.env.example` seguro.
- Ampliação de `.gitignore` e `.dockerignore`.
- Criação de `requirements-dev.txt` para instalação completa da API.
- CI ajustado para instalar dependências de autenticação e desenvolvimento.
- `STORAGE_ROOT` centralizado nas configurações da API.
- Financeiro e Compras passaram a usar o caminho configurável de armazenamento.
- Volume persistente de anexos adicionado aos Compose de desenvolvimento e produção.
- README atualizado conforme o estado real do projeto.
- Guia de instalação limpa e validação criado em `docs/STABILIZATION.md`.

## Próxima etapa

1. Executar instalação limpa na máquina de desenvolvimento.
2. Rodar migrations e testes.
3. Validar upload e leitura de anexos após recriação do container.
4. Implementar cliente HTTP central e tratamento de 401/403.
5. Implementar RBAC e proteção CSRF.
6. Criar os cadastros mestres antes dos novos módulos.
