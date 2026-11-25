# SÊNTICO V19 — Português, aparência clara/escura e Central de Notificações

**Base:** pacote completo V18 de 17/11/2026. Esta versão não é um patch isolado: contém o código-fonte integral e o instalador único.

## 1. O que mudou

### Tradução e apresentação de estados

- Status de OS usados em notificações passam a ter legendas em português no backend (`received`, `in_analysis`, `awaiting_quote`, `warranty`, `invoiced`, `no_repair`, etc.).
- O estado anterior **também é traduzido**, não apenas o estado atual.
- No painel e na central, notificações **já gravadas** também têm códigos/legendas conhecidos traduzidos ao serem exibidos; **não é necessário alterar seus registros no banco**.
- A duplicação do prefixo de OS é removida na apresentação: `OS OS-30740 · Warranty` aparece como `OS 30740 · Garantia`.
- Mensagens comuns de validação/API em inglês (`Field required`, `Not Found`, etc.) são traduzidas na interface.
- Não traduzimos texto livre inserido pelos colaboradores, nomes de marcas, modelos ou identificadores de integração.

### Central de Notificações

- Hierarquia visual refeita: resumo com quantidade de resultados e não lidas, cartões com ícone do setor, data, título, descrição e dados da OS/equipamento/responsável.
- Ação rápida para **Não lidas** e **Hoje**; pesquisa sempre visível; **Mais filtros** abre filtros por setor, ação, responsável, OS e período.
- Os filtros, a paginação, o botão **Abrir registro** e a marcação de leitura continuam usando a API existente.
- Ajuste de tamanhos e disposição para celulares, com campos ≥ 44 px e fonte ≥ 16 px nos controles de formulário.
- Regras de visibilidade da V18 **não foram alteradas**: Gestão acompanha todos os setores; ADM vê orçamentos; técnicos não recebem dados financeiros.
- Não reativamos pop-ups, Web Push, nem avisos fora do SÊNTICO.

### Tema Claro / Tema Escuro

- Novo controle **Aparência → Claro / Escuro** na barra lateral, visível em todos os módulos do SÊNTICO.
- Tema escuro permanece como padrão para não surpreender usuários atuais; o claro usa uma paleta de superfícies claras, textos escuros e bordas mais discretas.
- A escolha é guardada no armazenamento **local do navegador/dispositivo**. Outras abas abertas no mesmo navegador sincronizam o tema. Não há migração de banco nem mudança de permissões.
- O menu lateral permanece azul-marinho mesmo no modo claro para contraste da marca; a tela de login permanece com a arte escura por opção de identidade visual.
- CSS adicional do tema claro é escopado ao atributo `data-sentico-theme="claro"`, sem tocar nos estilos originais do tema escuro. Fotografia, logotipos e imagens não são invertidos.

## 2. Arquivos-chave

- `codigo-fonte/apps/web/src/shared/theme/theme.ts`
- `codigo-fonte/apps/web/src/shared/theme/ThemeSwitcher.tsx`
- `codigo-fonte/apps/web/src/shared/theme/theme-switcher.css`
- `codigo-fonte/apps/web/src/shared/theme/light-theme.css`
- `codigo-fonte/apps/web/src/shared/i18n/portugues.ts`
- `codigo-fonte/apps/web/src/shared/api/apiError.ts`
- `codigo-fonte/apps/web/src/shared/ui/SenticoSidebar.tsx`
- `codigo-fonte/apps/web/src/features/notifications/NotificationCenter.tsx`
- `codigo-fonte/apps/web/src/features/notifications/notification-center.css`
- `codigo-fonte/apps/web/src/features/dashboard/Dashboard.tsx`
- `codigo-fonte/apps/web/src/main.tsx`
- `codigo-fonte/apps/api/app/laboratory/router.py`

## 3. Validações executadas nesta entrega

- **56 arquivos TS/TSX** analisados pelo analisador sintático TypeScript: **0 erros sintáticos**.
- **28 testes do instalador**: aprovados.
- **16 testes de API** selecionados para status de laboratório e orçamento com fotos: aprovados.
- CSS do tema claro analisado por parser: **sem erros de parsing de topo**.
- Teste de tradução `OS OS-30740 · Warranty` → `OS 30740 · Garantia`: aprovado.
- Backend modificado passou em `py_compile`.

**Limitações:** não foi possível executar `npm run build` completo (dependências React não disponíveis localmente) nem teste real com Docker/PostgreSQL/Windows. A tentativa de inspeção gráfica automatizada no Chromium não concluiu. O contraste e a responsividade de cada módulo, inclusive modais e tabelas grandes, devem ser conferidos visualmente no Docker antes de atualizar a VPS. Os testes de instalação não substituem essa homologação.

## 4. Instalação local segura

1. Faça backup do banco PostgreSQL e do volume de uploads de seu ambiente atual.
2. Extraia o ZIP completo V19 em uma pasta nova no Windows, fora de `Arquivos de Programas`.
3. Abra o Docker Desktop (containers Linux).
4. Execute somente **`INICIAR_SENTICO.cmd`**; não use comandos que excluam volumes.
5. Após iniciar, abra **http://127.0.0.1:5184/** e atualize a aba (Ctrl+F5), se houver cache anterior.
6. No menu lateral, alterne **Claro / Escuro**, navegue por Painel, Laboratório, Estoque, Compras, Financeiro e Central de Notificações conforme seu perfil.
7. Abra a central, teste busca, filtros e o caso de uma OS que muda para **Garantia** com dois usuários autorizados.
8. Revise os formulários de estoque e orçamentos com fotos e o PDF. Atualize produção **somente** após homologação local.

**Preservação:** projeto Docker, volumes, instalador único e migração Alembic `20261117_01` da V18 foram mantidos. Não existe migração nova na V19. Nenhuma conexão ou atualização foi efetuada na VPS.
