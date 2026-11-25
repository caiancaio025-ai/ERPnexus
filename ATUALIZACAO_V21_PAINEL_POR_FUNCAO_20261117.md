# SÊNTICO V21 — Painel inteligente por função e contraste

Base: **V20**, mantendo V16–V20, incluindo temas, 10 fotos por orçamento e Central interna de Notificações.

## O que mudou

O **Painel inicial** agora consulta o servidor para montar filas de trabalho distintas conforme o perfil. As listas têm **contagem total** e mostram **até cinco itens** por quadro, evitando sobrecarregar a página. Abrir um item direciona ao contexto relevante, e **Ver no módulo** abre a lista completa. O painel atualiza automaticamente a cada minuto enquanto visível e ao voltar o foco para a janela.

| Perfil | Quadros exibidos |
| --- | --- |
| Gestão / Superadmin (legado) | Entradas do Laboratório, OS aprovadas, orçamentos a elaborar, solicitações de material a aprovar/comprar/receber, financeiro atrasado/pendente, últimos faturados, compras urgentes e notificações |
| ADM | Orçamentos a elaborar e notificações permitidas; sem quadro financeiro ou compras |
| LAB / Técnico / Laboratório | Equipamentos recebidos/aguardando análise, OS aprovadas e notificações permitidas, sem valores financeiros |
| Compras | Solicitações a aprovar, a comprar e aguardando chegada; central de pedidos atrasados/próximas entregas |
| Estoque | Materiais aguardando recebimento e itens já recebidos que precisam ser separados para o laboratório; links para Estoque |
| Consulta / demais | Apenas indicadores e avisos autorizados; nenhuma ação rápida irrelevante |

**Orçamentos a elaborar:** consulta OS no status `in_analysis` (apresentado como **Analisado**) ou `awaiting_quote`, desde que ainda **não exista orçamento emitido** para a OS. A revisão emitida não volta a ser listada como pendência. Os códigos internos dos status permanecem iguais.

**Financeiro da Gestão:** vencidos e pendentes baseados em lançamentos com status `pending`; os vencidos têm data inferior à data local (Recife). Os últimos faturados são OS com `invoiced_at` preenchido; a contagem mostra os últimos 30 dias e a lista traz as cinco emissões mais recentes. O painel não inventa valores nem calcula faturamento a partir de estimativas.

**Compras:** as solicitações vêm de `material_requests`, e os pedidos atrasados/próximas entregas de `purchase_orders`. A lista de compras mantém o filtro original. O status da solicitação é preservado.

## Navegação

- OS: `/laboratorio?os=<id>&aba=general|technical|quote|financial` (abre a OS correspondente).
- Pesquisa do topo: digitar OS/equipamento e pressionar **Enter** abre a pesquisa do Laboratório, sem restringir apenas ao mês atual.
- Solicitação: `/compras?view=requests&solicitacao=<id>` abre a solicitação exata, sem filtrar manualmente. Não reabre o modal repetidamente após salvar.
- Lançamento: `/financeiro?lancamento=<id>` abre a ficha do lançamento, com autorização da API.
- Estoque: leva ao módulo de Estoque. O vínculo com a solicitação fica descrito no quadro quando disponível.
- **Atividades recentes** e **Central de Notificações** continuam disponíveis sem pop-ups externos.

## Contraste no tema claro

- Corrigidos os botões de ação de **Colaboradores** (texto branco em fundo azul, botões Desativar/Reativar com texto branco em fundos fortes).
- Etiquetas **Ativo** (verde-claro + verde-escuro) e **Inativo** (rosa-claro + vermelho-escuro) mantêm significado e legibilidade.
- Quadros operacionais têm acentos discretos azul, âmbar, vermelho e verde, sem perder o tema branco. O painel é responsivo, com fontes e alvos de toque adequados em telas pequenas.

## Segurança

As filas são escolhidas **no backend**, não só escondidas com CSS. A consulta financeira só acontece no perfil **Gestão** (`gestao`/`super_admin`). O **ADM** recebe somente a fila de orçamento, mesmo se possuir permissões legadas para outros módulos. LAB não recebe valores e os perfis sem permissão não recebem links para ações financeiras. A API dos módulos continua validando a autorização nos destinos.

## Instalação e compatibilidade

1. **Faça backup do banco PostgreSQL e dos uploads antes de atualizar.**
2. Extraia o ZIP **inteiro** em uma pasta nova no Windows.
3. Abra Docker Desktop e execute **`INICIAR_SENTICO.cmd`**, o único inicializador.
4. Não execute `docker compose down -v` nem exclua volumes.
5. Confirme no navegador que o acesso local foi iniciado. Valide temas **Claro** e **Escuro** e o painel com usuários dos perfis Gestão, ADM, LAB e Compras; confira uma OS analisada sem orçamento, uma solicitação aprovada, um lançamento pendente/vencido e o link de cada registro.

**Nenhuma migração adicional de banco** foi introduzida pela V21. O projeto Compose, os nomes de volumes e o instalador único foram preservados. Nenhuma alteração foi feita na VPS.

## Validação deste pacote

- Testes específicos do painel no backend: **10 passaram**, com regra de visibilidade, segregação financeira e destinos de OS/Compras/Financeiro.
- Testes do instalador herdados da base V20: **40 passaram**.
- 56 arquivos `.ts`/`.tsx` analisados sintaticamente sem erros; os dois CSS modificados foram analisados sem erros de parsing.
- **Limitação:** a instalação offline dos pacotes NPM falhou por falta do cache de dependências. Portanto o **build completo do React e os testes visuais integrados no Docker/Windows não foram aprovados neste ambiente**. Teste no Docker local antes da VPS.
