# SÊNTICO V36 — Organização das NF-e e chaves de garantia

## Escopo da alteração

### Notas fiscais da OS (atendimento normal)
O quadro passa a reunir, nesta ordem:
1. NF de entrada;
2. NF de saída;
3. Chave NF de entrada (44 dígitos);
4. Chave NF de saída (44 dígitos).

As chaves existentes foram apenas movidas visualmente. Seus nomes e dados no banco continuam os mesmos (`entry_invoice_access_key` e `exit_invoice_access_key`).

### Garantias 1, 2 e 3
Cada cartão de garantia passa a oferecer quatro campos independentes:
- NF de entrada N;
- Chave NF de entrada N (44 dígitos);
- NF de saída N;
- Chave NF de saída N (44 dígitos).

Os novos campos são opcionais, aceitam somente 44 dígitos quando preenchidos e não reutilizam as chaves da OS normal. O backend valida o tamanho da chave antes de salvar.

## Migração do PostgreSQL

**Revisão nova:** `20261123_01` (descendente de `20261117_01`).

A migração adiciona seis colunas de texto de 44 caracteres, aceitando NULL, em `laboratory_work_orders`. Não exclui nem altera as NFs e chaves antigas. A rotina `INICIAR_SENTICO.cmd` chama o instalador, que reconhece as revisões anteriores e executa `alembic upgrade head` após as verificações de integridade e escrita.

**Faça backup verificado do banco PostgreSQL e dos uploads antes de instalar.** O pacote não realiza alterações na VPS. Não use `docker compose down -v` nem remova volumes.

## Arquivos alterados
- `codigo-fonte/apps/web/src/features/laboratory/LaboratoryDashboard.tsx`
- `codigo-fonte/apps/web/src/features/laboratory/types.ts`
- `codigo-fonte/apps/web/src/features/laboratory/laboratory.css`
- `codigo-fonte/apps/api/app/laboratory/models.py`
- `codigo-fonte/apps/api/app/laboratory/schemas.py`
- `codigo-fonte/apps/api/app/laboratory/router.py`
- `codigo-fonte/apps/api/app/laboratory/service.py`
- `codigo-fonte/apps/api/migrations/versions/20261123_01_warranty_invoice_access_keys.py`
- `codigo-fonte/apps/api/scripts/verificar_escrita_recuperacao.py`
- `INSTALAR_SENTICO.ps1`
- `scripts_recuperacao/catalogar_bancos_existentes.sh`
- `scripts_recuperacao/inspecionar_arquivo_pgdata.sh`
- testes automatizados e documentação.

## Homologação recomendada

1. Faça backup, extraia o ZIP em uma pasta nova e execute `INICIAR_SENTICO.cmd` com o Docker Desktop aberto.
2. Confira no log a revisão Alembic `20261123_01`.
3. Abra uma **OS existente com notas cadastradas** e confirme que NFs e chaves normais continuam preenchidas e aparecem juntas.
4. Em **Garantia 1**, informe uma chave de entrada válida de 44 dígitos e salve. Feche e reabra a OS: a chave deve permanecer.
5. Repita com saída de Garantia 1 e entradas/saídas das Garantias 2 e 3.
6. Teste deixar campos vazios, alterar somente uma chave e salvar sem alterar as outras.
7. Teste uma chave com menos de 44 dígitos: a API deve impedir o salvamento e informar o erro.
8. Verifique a visualização no celular e no desktop.

## Testes realizados nesta entrega
- Testes unitários dos seis campos, validação e preservação de NFs: aprovados.
- Migração de ensaio em banco SQLite descartável: aprovada, preservando os registros anteriores.
- Instalador: 45 testes aprovados.
- Verificação de sintaxe TS/TSX: 61 arquivos sem erros de parsing.
- `alembic heads`: uma cabeça identificada, `20261123_01`.
- Build integrado React/Vite e homologação Windows/Docker com PostgreSQL real: **pendentes**.

O módulo de orçamento (V35), as logos e os temas comemorativos permanecem inalterados.
