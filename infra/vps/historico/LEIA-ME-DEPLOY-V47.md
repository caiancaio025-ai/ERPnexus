> **Documento histórico da V47.** Os caminhos e comandos abaixo descrevem o procedimento antigo. Para aplicar a V48, siga [o guia atual](../LEIA-ME-DEPLOY.md). O script original foi preservado como `atualizar-v47.sh.txt` nesta pasta.

# Sêntico Green — histórico da implantação controlada V47

## Publicação da V48

A branch principal agora contém o código da V48. Enviar ou atualizar esse código pelo Git não substitui os containers em execução nem aplica alterações no banco da VPS. Consulte o `README.md` da raiz para instalação e testes locais da V48.

O script `infra/vps/atualizar.sh` continua restrito à implantação V47 descrita abaixo: ele verifica o commit homologado, a revisão inicial do banco e os IDs exatos das imagens V47. Essas verificações foram preservadas; o script bloqueia uma aplicação diferente, inclusive a V48. Ele não é o instalador nem o atualizador da V48.

A V48 mantém a revisão Alembic `20261123_02`. Sua implantação na VPS exige um procedimento próprio para construir e validar as imagens V48; trocar apenas a tag ou reutilizar as etapas V47 abaixo não atende a essa atualização.

## Procedimento histórico — somente V47

Procedimento específico para a V47 homologada em b98407ed0ed70c7b3e4185ffc4318c4e5ad14eb9. Não é um atualizador genérico. Não altera a aplicação homologada nem a configuração Compose. As imagens aprovadas na VPS são reutilizadas por tag e ID exatos.

1. Com o ERP em funcionamento, confira a main remota e faça fetch. Exija working tree limpa e atualização fast-forward para o commit de infraestrutura aprovado, sem reset/force.
2. Ative a manutenção com `python3 /root/sentico-manutencao/manutencao.py ativar`. Confira HTTP 503, API/web/gateway parados.
3. Execute `bash /opt/sentico-green/infra/vps/atualizar.sh` interativamente. Ele exige main sincronizada, revisão 20261117_01 e autorização MIGRAR V47. Faz backup novo do banco e dos uploads, restauração isolada estrita, hashes dos registros, migração e teste de readiness na cópia. Só depois migra o banco real para 20261123_02 e verifica registros. Não recria o banco, volumes ou gateway. Não faz rebuild.
4. Exija DEPLOY INTERNO V47 OK; MANUTENCAO ATIVA. Confirme relatório e saúde interna. Retire manutenção com `python3 /root/sentico-manutencao/manutencao.py voltar`. Confira HTTP 200 e API ready, login, garantia, pintura, orçamento e PDF.
5. Em erro, não repita cegamente. Leia a revisão real e logs em /root/backups-sentico/v47-deploy-*. Se a revisão for anterior, avalie retorno operacional com os containers antigos. Após a migração, mantenha manutenção, preserve backups e diagnostique antes de iniciar imagens antigas ou restaurar dados. O voltar.sh de infraestrutura falha fechado: downgrade automático proibido. Retirar manutenção não é rollback.

As sete verificações históricas de conciliação (CSV ausentes) e o teste opcional de desempenho permanecem pendentes. A generalização do deploy e rollback com CI deve ocorrer em outro commit, sem esta urgência.
