# SÊNTICO V46 — Fotos de envio e retorno na Mecânica / Pintura

## Correção

Esta atualização parte da **V45** e corrige o registro fotográfico de **Mecânica → Itens para pintura**.

- Cada peça/parte registrada no controle de pintura possui agora sua própria seção **Evidência da saída** e **Foto do retorno**.
- As fotos novas são salvas com o identificador da peça, da saída de pintura e da fase (`outbound`/`return`).
- O documento de imagem e o vínculo da foto são gravados **na mesma transação** do banco. Se a gravação falhar, o arquivo que acabou de ser enviado é descartado, evitando arquivos órfãos.
- Após o upload, a interface consulta novamente os dados no servidor e confirma que a foto está efetivamente listada na peça correspondente; caso contrário mostra erro.
- Depois de **Confirmar retorno completo**, as fotos de **envio e retorno continuam disponíveis** nas peças, em modo de consulta.
- Fotos registradas nas versões anteriores permanecem disponíveis em **Fotos anteriores deste controle (sem peça individual)**. O banco não tenta atribuí-las automaticamente a peças sem evidências dessa associação.
- Foram adicionadas mensagens claras de sucesso/erro e suporte a envio pela câmera e galeria, tanto no computador quanto no celular.
- A exclusão genérica de documentos passa a impedir a exclusão de imagens vinculadas ao histórico de pintura.

## Banco de dados

**Migração obrigatória:** `20261123_02_mechanical_painting_item_photos.py`, descendente de `20261123_01`.

Adiciona apenas uma coluna **opcional** `item_id` com chave estrangeira e índice à tabela `laboratory_mechanical_painting_photos`. As fotos anteriores mantêm o valor `NULL`, sem exclusão nem modificação de seus vínculos anteriores.

**Faça backup do banco PostgreSQL e do volume de uploads antes de atualizar.** Não execute comandos de remoção de volumes Docker.

## Instalação local

1. Faça backup do PostgreSQL e dos uploads.
2. Extraia o ZIP V46 em uma pasta nova.
3. Com o Docker Desktop aberto, execute **`INICIAR_SENTICO.cmd`**.
4. Confirme que o instalador concluiu a migração Alembic até **`20261123_02`** e reconstruíu **API e WEB**.
5. No navegador, atualize com `Ctrl + Shift + R`.

## Roteiro de homologação

1. Abra uma OS de teste → **Mecânica** → crie um controle com pelo menos duas peças para pintura.
2. Na primeira peça, anexe uma foto em **Evidência da saída** e verifique a confirmação.
3. Na segunda peça, anexe outra foto distinta. Feche e reabra a OS: ambas devem permanecer na peça certa.
4. Confirme a saída. As fotos de envio devem permanecer visíveis, sem opção de alterar essa fase.
5. Anexe uma **Foto do retorno** na primeira peça e outra na segunda. Feche e reabra: confirme os vínculos e as miniaturas.
6. Faça a conferência de cada peça e clique em **Confirmar retorno completo**. Reabra: **tanto envio quanto retorno** devem continuar visíveis.
7. Abra um controle de pintura anterior à V46 e confira as fotos históricas na seção de evidências antigas.
8. Repita no celular e nos temas claro/escuro.

## Validação realizada neste ambiente

- Testes de Mecânica, migração SQLite de ensaio, transação simulada (sucesso, falha e vínculo com peça errada), modelo de resposta e preservação no frontend.
- Instalação: testes estáticos dos scripts e segurança dos volumes.
- Gerador TypeScript: verificação sintática.

**Pendências:** não foi possível homologar em Docker/Windows com os dados reais nem executar o build completo do frontend sem as dependências React/Vite. A migração foi também compilada para DDL PostgreSQL, mas precisa ser executada no banco de homologação.

Não há alterações em valores de orçamento, regras financeiras, perfis ou na VPS de produção.
