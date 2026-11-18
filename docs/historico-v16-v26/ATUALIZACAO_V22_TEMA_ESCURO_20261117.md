# SÊNTICO V22 — Tema escuro com a identidade visual da versão clara

**Base:** SÊNTICO V21 de 17/11/2026. O pacote contém o projeto completo, instalador único e todas as correções da V21 e versões anteriores.

## Escopo

Esta atualização é **exclusivamente visual**. O tema claro, as regras de negócios, o backend, as permissões por perfil, as notificações internas, o histórico de OS, os orçamentos com até 10 fotos e o banco de dados permanecem inalterados.

- Cartões do painel e das filas de trabalho com gradientes suaves e mais profundidade, mantendo contagem e navegação por função.
- Áreas de Compras e notificações com bordas e cores contextuais, além de botões selecionados com fundo azul em degradê e texto branco.
- Status legíveis também em fundo escuro: vermelho para **Sem conserto**, verde para **Aprovado/Concluído**, âmbar para **Aguardando**, turquesa para **Analisado** e roxo para **Garantia/Faturado**.
- Notificações diferenciadas por setor, com faixas e pequenos detalhes coloridos, sem transmitir um status artificial.
- Módulos Financeiro, Laboratório, Compras, Estoque, Clientes e Colaboradores com elevação e contraste nas superfícies relevantes.
- Menu lateral, botões ativos, filtros e campos com foco visual claro, e suporte à preferência por movimento reduzido.
- **Não são usados gradientes em fotografias de equipamentos nem transformação de imagens.**

## Arquivos novos e alterados

- `codigo-fonte/apps/web/src/shared/theme/dark-elevated.css` — nova folha limitada a `html[data-sentico-theme="escuro"]`.
- `codigo-fonte/apps/web/src/main.tsx` — importa a folha após os estilos do tema claro.
- `testes_instalador/test_v22_tema_escuro.py` — regressões visuais/isolamento de tema.
- `LEIA_PRIMEIRO_SENTICO.md` — atualizado para V22.
- `previews/` — demonstrações sintéticas do CSS nos temas escuro e claro (não são capturas do ERP com dados reais).

Nenhuma revisão Alembic, migração, variável de ambiente, endpoint ou alteração no projeto Docker Compose foi introduzida.

## Validações realizadas

- Testes estáticos do instalador e de CSS (incluindo V22): **45 aprovados**.
- CSS da V22 validado com `tinycss2` (ausência de erros de sintaxe e isolamento de seletores ao tema escuro).
- Prévia renderizada no **Chromium headless** com os estilos reais do V21 e a nova folha da V22, incluindo o painel por função, notificações e filtros. Cores de fundo e texto inspecionadas nos dois temas.
- Tentativa de instalação de dependências: `npm ci --offline` **não concluiu**, pois o cache deste ambiente não contém `vite-8.1.4.tgz`. Consequentemente, o `npm run build` **não foi aprovado** neste ambiente. O build Docker/Windows e a revisão visual em todos os módulos permanecem pendentes.

## Instalação local segura

1. Faça backup de PostgreSQL e uploads antes de substituir qualquer versão utilizada com dados reais.
2. Extraia o ZIP V22 em uma **pasta nova**, sem misturar arquivos de versões anteriores.
3. Mantenha o Docker Desktop aberto e execute apenas **`INICIAR_SENTICO.cmd`**.
4. Acesse `http://127.0.0.1:5184/`, escolha **Tema escuro** em Aparência e confira Painel, Compras, Central de Notificações, Colaboradores, Laboratório, Estoque e Financeiro.
5. Compare o tema claro com a V21: não deve haver mudança. Confira também o celular e o modo com o menu recolhido.
6. Se a aparência antiga permanecer em cache, use `Ctrl+F5` ou reabra a versão instalada.

**Proteção dos dados:** não executar `docker compose down -v`, `docker volume prune` ou qualquer comando que remova volumes. Nenhuma alteração foi aplicada à VPS.
