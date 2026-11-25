# SÊNTICO V27 — Temas comemorativos com animações

## O que mudou

O SÊNTICO agora adapta pequenos elementos visuais às datas comemorativas, mantendo **todos os módulos, funcionalidades e permissões** da V26. A decoração é uma camada visual que **não bloqueia cliques, não modifica a disposição do conteúdo e não interfere nos status** do Laboratório.

| Período automático | Tema | Efeito visual |
|---|---|---|
| Fevereiro | Carnaval | Confetes coloridos e acentos suaves |
| Março ou abril, conforme o ano da Páscoa | Páscoa | Ovos e flores discretos, com movimento suave |
| Junho | São João / Festa Junina | Bandeirinhas coloridas e delicadamente animadas |
| Outubro | Halloween | Abóbora, lua e morcego com movimento sutil |
| Dezembro | Natal | **Neve caindo e luzes coloridas piscando** |
| Demais meses | Tema normal | Sem decoração comemorativa |

A data da Páscoa é calculada pelo calendário gregoriano. Como o Carnaval foi solicitado para **o mês de fevereiro**, o tema de Carnaval fica ativo durante fevereiro, independentemente de mudanças na data oficial de Carnaval.

## Como ativar, desativar ou testar fora de época

1. Entre no SÊNTICO e abra o menu lateral.
2. Abaixo de **Aparência → Claro / Escuro**, encontre **Temas comemorativos**.
3. Escolha **Automático pela data** (padrão), **Desativado** ou uma data específica para prévia, como **Natal (prévia)**.
4. Use **Animar decoração** para desligar somente os movimentos; os detalhes estáticos continuam visíveis.
5. Com o menu recolhido, o ícone de estrelas permite ligar/desligar os temas automáticos.

A preferência é salva **neste navegador/dispositivo**. O claro/escuro permanece independente dos temas comemorativos. O sistema respeita a opção de acessibilidade do dispositivo para reduzir movimento (`prefers-reduced-motion`).

## Proteção de usabilidade e desempenho

- Efeitos decorativos usam `pointer-events: none`, sem capturar cliques de botões ou formulários.
- Não há imagens externas nem dependências JavaScript adicionais; neve, luzes e bandeirinhas são criadas em CSS e componentes leves.
- A quantidade de partículas cai em telas pequenas.
- Animações são suprimidas automaticamente para quem solicita movimento reduzido.
- A decoração é omitida nos documentos impressos.
- Sem mudança de cor de status, de regras de negócio, tabelas, consultas da API, perfis ou autorizações.
- A mudança de mês é verificada ao voltar à aba e periodicamente enquanto o sistema estiver aberto.

## Arquivos alterados

- `codigo-fonte/apps/web/src/shared/theme/seasonal.ts` — calendário, configuração e persistência.
- `codigo-fonte/apps/web/src/shared/theme/SeasonalDecorations.tsx` — elementos de decoração.
- `codigo-fonte/apps/web/src/shared/theme/seasonal.css` — cores, efeitos e regras responsivas.
- `codigo-fonte/apps/web/src/shared/theme/ThemeSwitcher.tsx` — seleção manual e automática.
- `codigo-fonte/apps/web/src/shared/theme/theme-switcher.css` — estilo dos controles.
- `codigo-fonte/apps/web/src/main.tsx` — inicialização do tema comemorativo.
- `codigo-fonte/apps/web/src/app/App.tsx` — ativação visual após o login.
- `testes_instalador/test_v27_temas_comemorativos.cjs` — testes de calendário e preferências.

## Banco e instalação

**Nenhuma migração de banco**. Preservados o projeto Compose `sentico-v14-recuperado`, os volumes do Docker e o instalador único `INICIAR_SENTICO.cmd`.

Faça backup do banco PostgreSQL e dos uploads, extraia o pacote inteiro em uma nova pasta, abra o Docker Desktop e execute **`INICIAR_SENTICO.cmd`**. O ambiente local continua em http://127.0.0.1:5184/ conforme o guia do instalador.

## Testes realizados

- 18 verificações Node.js da lógica de calendário, temas automáticos/manuais, configuração e acessibilidade: **aprovadas**.
- 45 testes automáticos do instalador: **aprovados**.
- Análise sintática de 58 arquivos TS/TSX: **sem erros de sintaxe**.
- CSS da decoração e do controle: **sem erros de parsing**.
- Teste isolado de CSS no Chromium em larguras de 390 e 1366 px: neve animada, luzes coloridas, camada sem interceptação de cliques e sem rolagem horizontal.

**Limitação:** o teste isolado de CSS não é o mesmo que homologação do ERP real. A compilação integral com dependências NPM, a renderização de todos os módulos e os testes integrados Docker/PostgreSQL/Windows ainda precisam ser executados localmente. Nenhum dado real ou VPS foi atualizado.
