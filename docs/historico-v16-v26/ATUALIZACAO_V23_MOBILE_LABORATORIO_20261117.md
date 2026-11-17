# SÊNTICO V23 — Correções mobile do Laboratório

## Objetivo
Ajustar a experiência do módulo **Laboratório** no celular, principalmente na listagem de O.S. e na tela de detalhe da O.S., preservando todas as informações importantes sem comprimir o conteúdo.

## Problemas corrigidos

- Número da O.S. aparecendo quebrado / “na vertical” na listagem mobile.
- Colunas da lista de O.S. comprimidas, dificultando a leitura de cliente, equipamento e status.
- Status pouco visível ou oculto na listagem do Laboratório no celular.
- Abas do detalhe da O.S. sobrepostas ou desconfortáveis em telas estreitas.
- Cabeçalho e ações do detalhe da O.S. com distribuição inadequada em telas pequenas.

## Ajustes realizados

### 1) Lista de O.S. do Laboratório no celular
- A tabela passa a assumir **layout de cartões** abaixo de 760 px.
- Cada O.S. é exibida como um bloco próprio, com rótulos por campo.
- O número da O.S. fica em destaque e na horizontal.
- Cliente, equipamento e status ocupam largura total do cartão para melhor leitura.
- Localização, NFs, prioridade, data e valor mantêm leitura adequada e quebra de linha segura.

### 2) Detalhe da O.S. no celular
- Cabeçalho reorganizado para permitir quebra correta de textos longos.
- Área de ações com melhor distribuição dos botões.
- Abas da O.S. adaptadas para botões maiores e mais fáceis de tocar.
- Rodapé com ações empilhadas no mobile para evitar aperto e sobreposição.

## Arquivos alterados

- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `codigo-fonte/apps/web/src/shared/theme/light-theme.css`
- `LEIA_PRIMEIRO_SENTICO.md`

## Banco / infraestrutura

- **Sem migração de banco**
- **Sem alteração de volumes Docker**
- **Sem alteração no instalador único**
- **Sem mudança de permissões ou regras de negócio**

## Como validar localmente

1. Extraia o pacote em uma pasta nova.
2. Abra o Docker Desktop.
3. Execute `INICIAR_SENTICO.cmd`.
4. Acesse o módulo **Laboratório**.
5. Teste a listagem e o detalhe da O.S. em largura de celular no navegador (ex.: 360×800 ou 390×844).
6. Verifique principalmente:
   - leitura do número da O.S.;
   - visibilidade do status;
   - organização das abas;
   - conforto de uso dos botões de ação;
   - preservação do layout no desktop.

## Observação
Esta versão é corretiva e focada em **responsividade mobile do Laboratório**.
