# Deploy do Sêntico Green (ERP) por git — VPS

O código oficial fica neste repositório (GitHub `caiancaio025-ai/ERPnexus`). A VPS clona o repo
e sobe a aplicação em Docker (projeto `sentico-green-hml`): Postgres, API (FastAPI), Web (React/Caddy)
e o gateway (Caddy). Os volumes de dados (banco e uploads) são **externos** — o deploy nunca os apaga.

## Fluxo das próximas atualizações (o que você vai fazer)

1. **No seu PC** (pasta do projeto, já clonada): faça as alterações e rode `enviar.bat`
   (ele faz `git add` + `commit` + `push` para o GitHub).
2. **Na VPS** (como root):
   ```
   bash /opt/sentico-green/infra/vps/atualizar.sh
   ```
   Ele faz, em ordem: `git pull` → **backup fresco** → guarda as imagens atuais (rollback) →
   **build** das imagens novas → **PORTÃO**: testa a migração numa **cópia** do banco (não destrutivo)
   → **cutover** (migra o banco real e sobe o novo) → confere a saúde e a borda.
   - Se o **portão falhar**, nada é alterado em produção.
   - No fim mostra `ATUALIZADO: ... no ar` ou um alerta com o caminho do rollback.

## Instalação (uma vez só)

> O V15 já está no ar. Isto só liga a VPS ao git para as **próximas** atualizações; não re-sobe o sistema.

Na VPS, como root, com o `instalar.sh` em mãos:
```
bash instalar.sh
```
Na primeira vez ele gera uma **chave de deploy (só leitura)** e pede para você cadastrá-la em
`GitHub > ERPnexus > Settings > Deploy keys`. Depois rode `instalar.sh` de novo: ele clona o repo em
`/opt/sentico-green`, reconstrói o `.env.production` a partir dos containers em execução e grava a TAG atual.

## Voltar (rollback)

```
bash /opt/sentico-green/infra/vps/voltar.sh
```
Sobe de volta as imagens `:anterior` (api e web). Se a atualização mexeu no banco, o script mostra como
restaurar o backup `pre-deploy` feito automaticamente antes da troca.

## Segurança / dados

- `.env.production` (senhas, DATABASE_URL, GEMINI, etc.) **não** vai para o git (está no `.gitignore`).
  Ele é reconstruído na VPS a partir dos containers. Guarde uma cópia offsite (o backup diário já inclui).
- Volumes `sentico-green-hml_green_postgres_data` e `_uploads_data` são **externos**: o deploy os usa,
  nunca os cria nem apaga.
- O gateway e o web usam Caddy 2.10 com `cap_add: [NET_BIND_SERVICE]` no compose — isso evita o erro
  `exec /usr/bin/caddy: operation not permitted` quando se usa `cap_drop: [ALL]`.

## Backup offsite

Os scripts em `infra/vps/offsite/` configuram o backup diário (banco + uploads + env) e a cópia puxada
para a máquina Windows. Veja o pacote de configuração entregue à parte.
