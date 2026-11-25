# SÊNTICO V15 — INSTALAÇÃO WINDOWS

**A V15 é a V14 estável com a nova interface de Estoque.** O inicializador por compatibilidade foi mantido integralmente. Não renomeie ou apague volumes Docker.

## INSTALAÇÃO OU ATUALIZAÇÃO LOCAL

1. Preserve o backup de seu ambiente. No Docker Desktop, não exclua os volumes existentes.
2. Extraia TODO o conteúdo deste ZIP em uma pasta no Windows (não execute arquivos dentro do ZIP).
3. Abra o Docker Desktop e espere ele ficar operacional.
4. Execute `INICIAR_SENTICO_V15.cmd` por duplo clique. O atalho usa o mesmo `INICIAR_SENTICO_V14.cmd` e `INSTALAR_SENTICO_V14.ps1` já aprovados na V14.
5. Quando o instalador indicar sucesso, abra http://127.0.0.1:5184/ e entre com seus usuários existentes.

**AVISO:** não execute `docker compose down -v`, `docker volume rm` ou comandos de limpeza de volumes. O instalador tem descoberta por compatibilidade e pode executar migrations caso a versão do banco esteja atrasada. Faça backup prévio se essa for sua instalação de trabalho.

## O QUE FOI MODIFICADO NA V15

- Criação facilitada de endereços com código automático para estantes, gavetas, caixas e galerias.
- Criação de vários locais em sequência, com pré-visualização antes de salvar.
- Cards de busca com foto, nome, quantidade, descrição, formato e endereço.
- Novo layout de etiqueta PDF para impressão, mantendo código e QR.

## ESTRUTURA E COMPATIBILIDADE

- O instalador Windows e os arquivos Docker Compose permanecem os mesmos da V14 compatível.
- Os volumes padrão da recuperação são `sentico-v14-recuperado_pgdata`, `sentico-v14-recuperado_uploads`, `sentico-v14-recuperado_node_modules`; o instalador reconhece os volumes reais do projeto.
- A senha de acesso ao banco da recuperação é preservada em `%LOCALAPPDATA%\Sentico\RecuperacaoV14\.env.recuperacao`. Não envie esse arquivo, senhas ou arquivos do banco.
- Este ZIP NÃO inclui banco de dados, fotos/arquivos privados, senhas, backups ou pacotes locais de node_modules.
- A V15 é uma atualização local Windows, não foi destinada à VPS Hostinger.

## ARQUIVOS ALTERADOS

- `codigo-fonte/apps/web/src/features/inventory/InventoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/inventory/inventory.css`
- `codigo-fonte/apps/api/app/inventory/label_pdf.py`
- `INICIAR_SENTICO_V15.cmd` (atalho que chama o instalador V14 preservado).

## VALIDAÇÕES DESTA ENTREGA

- `npm run build` em apps/web: TypeScript + Vite concluídos.
- `python -m py_compile` na etiqueta e arquivos da API: aprovado.
- ZIP verificado e conteúdo comparado ao instalador Windows V14 estável.
- O Docker Desktop real no notebook do usuário NÃO foi acessado nesta execução; homologar localmente antes de qualquer produção.
