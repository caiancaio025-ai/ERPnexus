# Arquitetura inicial

```text
Navegador
  ├─ empresa.com.br      -> Caddy -> site Astro
  └─ app.empresa.com.br  -> Caddy -> ERP React
                                 └─ /api -> FastAPI -> PostgreSQL
```

O banco permanece na rede Docker e não possui porta pública em produção. O frontend nunca acessa banco, chave Gemini ou credenciais. O backend concentra domínio, autorização, auditoria e integrações.

Os módulos vazios em `apps/api/app` representam limites de domínio definidos no SDD. Eles não contêm código genérico. Cada módulo receberá regras somente quando a fase correspondente começar.
