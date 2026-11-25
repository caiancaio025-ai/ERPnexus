# SÊNTICO V15 — Atualização de identidade visual (12/11/2026)

## Base preservada
Este projeto foi construído diretamente do arquivo enviado pelo usuário:
`SENTICO_V15_COMPLETO_INSTALADOR_WINDOWS_20261103 (3).zip`.

Não foram usados os pacotes posteriores de instalação/conta ADM. O instalador Windows, o
Docker Compose e o backend permanecem **sem alterações**.

## Alterações
- Substituição da marca antiga pelos arquivos oficiais enviados (horizontal, símbolo e ícone do aplicativo).
- Login com logo horizontal e rodapé jurídico elegante: "© [ano atual] SÊNTICO® · Todos os direitos reservados."
- Favicons PNG/ICO, ícone Apple Touch e manifest PWA/atalho atualizados.
- Logo horizontal nas barras abertas. Símbolo isolado nas barras recolhidas.
- Menu principal do painel agora permite recolher/expandir no desktop.
- Ajustes de identidade também em Clientes, Financeiro, Compras, Comercial e Colaboradores.

## Instalação no Windows
1. Para uma instalação separada: extraia o ZIP completo e execute o **mesmo**
   `INICIAR_SENTICO_V15.cmd` que existia na base estável.
2. Para atualizar os arquivos da instalação existente: use o ZIP de alterações
   sobre a raiz do projeto, mantendo as subpastas. Em seguida atualize o frontend.
3. Para ver o favicon novo, feche/abra a guia ou faça atualização forçada (`Ctrl+F5`).

**Importante:** se a instalação anterior for de dados reais, mantenha backup dos
volumes PostgreSQL e uploads. Não execute `docker compose down -v` nem renomeie
volumes. Esta atualização não exige migrations nem mudanças no banco.

## Validação
- Build: `npm run build` (TypeScript + Vite), concluído com sucesso.
- Prévia de login testada em layout desktop e mobile sem sobreposição do rodapé.
- Integridade do ZIP e preservação byte a byte do instalador Windows verificadas.
- Não há homologação de execução completa no Docker Desktop Windows neste ambiente.

## Observação sobre a marca
O texto SÊNTICO® aparece conforme solicitado pelo titular do projeto. A
situação registral da marca não foi verificada nesta atualização.
