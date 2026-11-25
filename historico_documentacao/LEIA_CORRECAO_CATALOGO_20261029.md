# Correcao da etapa 06 - Catalogo do PostgreSQL

## Problema observado

A autenticacao TCP passou, mas o instalador parou com `ERRO_CATALOGO_POSTGRESQL`.
O script de catalogacao era enviado ao container por pipeline `Get-Content -Raw | docker compose exec -T db sh -s`. Em falhas, o instalador ocultava o diagnostico. Alem disso, o teste de autenticacao usava o IP do container enquanto a catalogacao tentava socket ou 127.0.0.1.

## Correcao

- Copia o script local para `/tmp` do proprio container com `docker cp` e o executa com `docker exec ... sh`, sem pipeline PowerShell.
- Executa SELECTs via o mesmo IP TCP do container usado no teste de autenticacao.
- Mostra apenas codigos de diagnostico e metadados (nome do banco, revisao, contagens), sem senhas ou registros individuais.
- Nao cria bancos, nao apaga volumes, nao restaura backup nem altera senhas nesta etapa.
- Mantem EXATAMENTE os volumes externos: `sentico-v14-recuperado_pgdata`, `sentico-v14-recuperado_uploads`, `sentico-v14-recuperado_node_modules`.
- Mantem a barreira contra migrations quando nao houver banco validado.

## Aplicacao

1. Preserve backups e volumes atuais.
2. Substitua `INSTALAR_SENTICO_V14.ps1` e `scripts_recuperacao/catalogar_bancos_existentes.sh` pelos arquivos deste pacote.
3. Execute `INICIAR_SENTICO_V14.cmd`.
4. Se houver erro, envie somente as linhas iniciadas em `CATALOGO:` e a mensagem final, nao envie `.env`, senhas ou backups.

O teste integral depende da execucao no Docker Desktop Windows. Os testes de shell e os testes de contrato nao substituem a homologacao no ambiente real.
