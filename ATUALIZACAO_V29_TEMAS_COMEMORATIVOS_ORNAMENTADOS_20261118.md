# SÊNTICO V29 — Temas comemorativos ornamentados

## Objetivo
Implementar no código-fonte do ERP o acabamento festivo mostrado nas prévias, em vez de entregar apenas imagens estáticas. Base de trabalho: **V28**, com todas as funcionalidades anteriores preservadas.

## O que foi implementado

### Halloween (outubro)
- Decoração com abóboras, doces, pirulitos, caveiras, ossos, teias e morcegos.
- Arte ornamental em um painel comemorativo real, sem cobrir indicadores ou botões.
- Cores temáticas discretas nos contornos.

### Carnaval (fevereiro)
- Arte com máscaras e elementos da festa.
- Sombrinhas de frevo, fitas e maior densidade de confetes animados.
- Cores festivas sem interferir nas cores semânticas de status.

### Ano-Novo (janeiro)
- Arte de champanhe/taças, fogos de artifício ampliados.
- Saudação dinâmica calculada a partir do calendário: **Feliz 2027!** para a virada 2026–2027.
- Permanece a escolha de tema automático ou prévia manual.

### Demais festas
- **Natal:** novembro e dezembro, neve e luzes coloridas preservadas, com faixa comemorativa ilustrada.
- **Páscoa:** mês em que a data cai em cada ano, com elementos florais, coelho e ovos.
- **São João:** junho, bandeirinhas, girassóis e ornamentos da festa.

## Uso
No menu lateral do SÊNTICO, vá a **Aparência → Temas comemorativos** para usar o modo automático, selecionar uma festa em prévia ou desativar os temas. **Animar decoração** desliga os efeitos sem remover o painel; o sistema também respeita `prefers-reduced-motion`.

## Arquivos modificados
- `codigo-fonte/apps/web/src/shared/theme/SeasonalDecorations.tsx`
- `codigo-fonte/apps/web/src/shared/theme/SeasonalDashboardBanner.tsx` (novo)
- `codigo-fonte/apps/web/src/shared/theme/seasonal.css`
- `codigo-fonte/apps/web/src/features/dashboard/Dashboard.tsx`
- `codigo-fonte/apps/web/public/temas-comemorativos/*.webp` (seis artes derivadas das prévias geradas nesta conversa)
- `testes_instalador/test_v27_temas_comemorativos.cjs` (atualização das expectativas da V28)
- `testes_instalador/test_v29_decoracao_premium.cjs` (novo)

## Limites e segurança
- Nenhuma alteração de API, permissões, banco de dados, Docker Compose, volumes ou instalador.
- As imagens são decorativas; os controles reais continuam componentes React.
- As imagens ficam na própria aplicação, sem dependências externas durante a execução.
- Antes de atualizar a VPS, **faça backup e homologue no Docker local**, verificando tema claro/escuro, Android/iPhone e ausência de obstrução dos controles.

## Validação executada neste pacote
- 19 testes de calendário/preferências: **aprovados**.
- 11 testes direcionados da decoração V29: **aprovados**.
- 23 testes selecionados de compatibilidade/instalador: **aprovados**.
- Verificação sintática TypeScript/TSX: **59 arquivos, sem erros de sintaxe**.
- Parser CSS: **sem erros**.
- Build integral React/Vite: **não executado**, dependências não disponíveis offline.
- Captura automatizada Chromium: **não concluída**; requer homologação visual real.
