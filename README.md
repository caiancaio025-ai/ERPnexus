# SÊNTICO / ERPnexus — V48

Versão de 25/11/2026 com correções de gravação em Compras e ordens de serviço, preservação de campos em edições, controle de operações simultâneas e recuperação de falhas de comunicação.

## Instalação local no Windows

1. Faça backup do banco e dos uploads da instalação existente.
2. Baixe e extraia o repositório completo, ou utilize um checkout atualizado da branch `main`.
3. Abra o Docker Desktop com containers Linux.
4. Execute **`INICIAR_SENTICO.cmd`** na raiz e aguarde `SENTICO_INICIADO=OK`.
5. Acesse **http://127.0.0.1:5184/** e pressione Ctrl+F5.
6. Confira **http://127.0.0.1:5184/api/health/version**: deve informar `"version":"48"`.

O instalador preserva o projeto operacional `sentico-v14-recuperado` e reutiliza os volumes existentes de PostgreSQL e uploads. Não remova volumes para atualizar. A V48 não acrescenta migração de estrutura; a revisão atual permanece `20261123_02`.

Leia o procedimento completo em [LEIA_PRIMEIRO_SENTICO.md](LEIA_PRIMEIRO_SENTICO.md).

## Correções principais

- Compras e solicitações preservam informações não editadas e retornam corretamente o destino de estoque.
- Reenvio de anexo usa a compra já confirmada; recebimentos e numeração possuem proteção contra concorrência.
- A edição de OS envia apenas os campos modificados e verifica a versão antes de gravar.
- Falhas de consulta posteriores a uma gravação confirmada não são apresentadas como falha de salvamento.
- Ajustes em Orçamentos, Estoque, Comercial, Financeiro, Clientes, Colaboradores e Notificações.
- Interface operacional compilada e API sem recarga automática de código.

O [relatório V48](RELATORIO_V48_ESTABILIDADE_E_TESTES.md) descreve causas, alterações e limites da validação.

## Testes

A validação da versão entregue terminou com **665 testes Python aprovados, zero falhas e sete testes históricos ignorados** por ausência dos CSVs privados necessários. Também passaram a compilação TypeScript/Vite, 18 testes JavaScript, 61 verificações adicionais, 18 cenários de navegador com respostas controladas e 12 verificações de navegador com API/PostgreSQL reais.

Execute **`TESTAR_SENTICO.cmd`** para repetir os testes automatizados em um banco temporário separado. O projeto `sentico-v48-testes` não publica portas nem monta volumes operacionais. O resultado fica em `resultados_testes/api-e-instalador.xml`.

Após adaptar os caminhos para este repositório, a suíte foi executada novamente no checkout: **665 aprovados, sete ignorados e nenhuma falha**. O build da interface e os testes JavaScript também passaram. Os resultados desta conferência têm prefixo `github-` na pasta de evidências.

As evidências da entrega estão em [validacao_v48](validacao_v48/). Os testes de navegador ficam em `apps/web/tests/browser-reliability.py` e exigem Playwright/Chromium. O ambiente Windows/Docker operacional não foi acessado durante a validação registrada.

## Organização

| Caminho | Conteúdo |
|---|---|
| `apps/api/` | API FastAPI, migrações, dependências fixadas e testes. |
| `apps/web/` | Interface React/TypeScript, build Vite e testes. |
| `compose.recuperacao.yml` | Instalação local gerenciada por `INICIAR_SENTICO.cmd`. |
| `compose.tests.yml` | Ambiente descartável de testes. |
| `compose.dev.yml` | Ambiente de desenvolvimento separado. |
| `testes_instalador/` | Verificações do instalador e de compatibilidade. |
| `scripts_recuperacao/` | Ferramentas usadas pelo instalador local. |
| `infra/vps/` | Infraestrutura e procedimentos existentes da VPS. |

O repositório mantém a estrutura anterior com `apps/` na raiz. No ZIP V48 entregue na conversa, a mesma aplicação fica em `codigo-fonte/apps/`; somente os caminhos de instalação e teste foram adaptados para este repositório.

## Atualização da VPS Hostinger

O atualizador da VPS foi adaptado para **V47 → V48**. No terminal do servidor, como root:

```bash
cd /opt/sentico-green &&
git pull --ff-only origin main &&
bash infra/vps/atualizar.sh
```

Ele verifica a instalação, constrói as imagens V48, faz backup, ativa manutenção temporária e troca somente API/interface, com retorno às imagens anteriores se a conferência interna falhar. A revisão do banco permanece `20261123_02`.

Aguarde **`SENTICO_V48_ATUALIZADO=OK`**. Publicar ou baixar o código pelo Git ainda não executa essa implantação; é necessário rodar o atualizador no servidor. Veja [infra/vps/LEIA-ME-DEPLOY.md](infra/vps/LEIA-ME-DEPLOY.md) para resultados, limitações e registros de recuperação.

O atalho antigo `TESTAR-V26-LOCAL.cmd` encaminha para `TESTAR_SENTICO.cmd`, sem trocar a branch atual. Procedimentos V26/V47 anteriores foram preservados como histórico.

## Diagnóstico

Execute **`DIAGNOSTICAR_SENTICO.cmd`** para consultar versão, disponibilidade da API/banco, reinícios e volumes. Se uma gravação tiver resultado incerto por perda de conexão, consulte o registro antes de reenviar e anote a referência exibida na mensagem.
