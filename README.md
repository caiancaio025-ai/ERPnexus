# SÊNTICO / ERPnexus — V48

V48 com correções de gravação em Compras e ordens de serviço. A atualização de **26/11/2026** acrescenta Aparência no cabeçalho e recebimento individual com quantidade da compra e códigos EST automáticos. Veja [as alterações e a validação](ATUALIZACAO_V48_APARENCIA_ESTOQUE.md).

## Experimentar esta atualização no Windows

Esta versão inclui a atualização de **26/11/2026**, com as correções de aparência e recebimento e um ambiente separado para avaliação local.

Extraia todo o ZIP em uma pasta própria, abra o Docker Desktop com containers Linux e execute **`INICIAR_TESTE_V48.cmd`**. Ele prepara um banco separado, cria um usuário de teste e abre o sistema, por padrão em **http://127.0.0.1:5185/**. O endereço final e as credenciais aparecem ao terminar. Para encerrar, use **`PARAR_TESTE_V48.cmd`**; os dados de teste ficam disponíveis na próxima abertura.

O projeto do teste manual é `sentico-v48-teste-local`, com volumes próprios. O roteiro e os resultados esperados estão em [COMECE_AQUI_TESTE_V48.txt](COMECE_AQUI_TESTE_V48.txt). `INICIAR_SENTICO.cmd`, descrito abaixo, é o instalador da versão operacional.

## Instalação local no Windows

1. Faça backup do banco e dos uploads da instalação existente.
2. Baixe e extraia o repositório completo, ou utilize um checkout atualizado da branch `main`.
3. Abra o Docker Desktop com containers Linux.
4. Execute **`INICIAR_SENTICO.cmd`** na raiz e aguarde `SENTICO_INICIADO=OK`.
5. Acesse **http://127.0.0.1:5184/** e pressione Ctrl+F5.
6. Confira **http://127.0.0.1:5184/api/health/version**: deve informar `"version":"48"`.

O instalador preserva o projeto operacional `sentico-v14-recuperado` e reutiliza os volumes existentes de PostgreSQL e uploads. Não remova volumes para atualizar. Esta atualização aplica a migração incremental `20261126_01`, para vincular várias unidades individuais à mesma compra, preservando os registros anteriores.

Leia o procedimento completo em [LEIA_PRIMEIRO_SENTICO.md](LEIA_PRIMEIRO_SENTICO.md).

## Correções principais

- Aparência, nome do usuário e Sair ficam no cabeçalho; as opções de tema abrem em um painel compacto.
- Recebimento individual usa a quantidade da compra, gera uma etiqueta EST por unidade e torna a série do fabricante opcional.
- Compras e solicitações preservam informações não editadas e retornam corretamente o destino de estoque.
- Reenvio de anexo usa a compra já confirmada; recebimentos e numeração possuem proteção contra concorrência.
- A edição de OS envia apenas os campos modificados e verifica a versão antes de gravar.
- Falhas de consulta posteriores a uma gravação confirmada não são apresentadas como falha de salvamento.
- Ajustes em Orçamentos, Estoque, Comercial, Financeiro, Clientes, Colaboradores e Notificações.
- Interface operacional compilada e API sem recarga automática de código.

O [relatório V48](RELATORIO_V48_ESTABILIDADE_E_TESTES.md) descreve causas, alterações e limites da validação.

## Testes

A validação da entrega inicial de 25/11 terminou com **665 testes Python aprovados, zero falhas e sete testes históricos ignorados** por ausência dos CSVs privados necessários. Também passaram a compilação TypeScript/Vite, 18 testes JavaScript, 61 verificações adicionais, 18 cenários de navegador com respostas controladas e 12 verificações de navegador com API/PostgreSQL reais.

Execute **`TESTAR_SENTICO.cmd`** para repetir os testes automatizados em um banco temporário separado. O projeto `sentico-v48-testes` não publica portas nem monta volumes operacionais. O resultado fica em `resultados_testes/api-e-instalador.xml`.

Após adaptar os caminhos para este repositório, a suíte foi executada novamente no checkout: **665 aprovados, sete ignorados e nenhuma falha**. O build da interface e os testes JavaScript também passaram. Os resultados desta conferência têm prefixo `github-` na pasta de evidências.

Os resultados da atualização de 26/11 estão no [relatório de aparência e recebimento](ATUALIZACAO_V48_APARENCIA_ESTOQUE.md). As evidências, incluindo as da entrega inicial, estão em [validacao_v48](validacao_v48/). Os testes de navegador ficam em `apps/web/tests/browser-reliability.py` e exigem Playwright/Chromium. O ambiente Windows/Docker operacional não foi acessado durante a validação registrada.

## Organização

| Caminho | Conteúdo |
|---|---|
| `apps/api/` | API FastAPI, migrações, dependências fixadas e testes. |
| `apps/web/` | Interface React/TypeScript, build Vite e testes. |
| `compose.teste-local.yml` | Teste manual isolado, iniciado por `INICIAR_TESTE_V48.cmd`. |
| `compose.recuperacao.yml` | Instalação local gerenciada por `INICIAR_SENTICO.cmd`. |
| `compose.tests.yml` | Ambiente descartável de testes. |
| `compose.dev.yml` | Ambiente de desenvolvimento separado. |
| `testes_instalador/` | Verificações do instalador e de compatibilidade. |
| `scripts_recuperacao/` | Ferramentas usadas pelo instalador local. |
| `infra/vps/` | Infraestrutura e procedimentos existentes da VPS. |

O repositório e este ZIP mantêm `apps/` na raiz. O ZIP inicial de 25/11 usava `codigo-fonte/apps/`. As alterações de aparência e recebimento e os atalhos de avaliação local estão incluídos nesta versão.

## Atualização da VPS Hostinger

O atualizador da VPS aplica esta atualização sobre **V47 ou V48** nas revisões de banco reconhecidas. Para aplicar o código atualizado, no terminal do servidor, como root:

```bash
cd /opt/sentico-green &&
git pull --ff-only origin main &&
bash infra/vps/atualizar.sh
```

Ele verifica a instalação, constrói as imagens V48, ativa manutenção temporária e faz backup. Ensaia a migração em uma cópia isolada antes de aplicá-la no banco existente; depois troca API/interface e confere os arquivos servidos. A revisão final é `20261126_01`. Em caso de falha, tenta recuperar as imagens anteriores sem restaurar ou rebaixar o banco.

Aguarde **`SENTICO_V48_ATUALIZADO=OK`**. Publicar ou baixar o código pelo Git ainda não executa essa implantação; é necessário rodar o atualizador no servidor. Veja [infra/vps/LEIA-ME-DEPLOY.md](infra/vps/LEIA-ME-DEPLOY.md) para resultados, limitações e registros de recuperação.

O atalho antigo `TESTAR-V26-LOCAL.cmd` encaminha para `TESTAR_SENTICO.cmd`, sem trocar a branch atual. Procedimentos V26/V47 anteriores foram preservados como histórico.

## Diagnóstico

Execute **`DIAGNOSTICAR_SENTICO.cmd`** para consultar versão, disponibilidade da API/banco, reinícios e volumes. Se uma gravação tiver resultado incerto por perda de conexão, consulte o registro antes de reenviar e anote a referência exibida na mensagem.
