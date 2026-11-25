# SÊNTICO V40 — Endereço das empresas emitentes

## Correção
O cadastro de **Empresas emitentes**, na área Comercial, já possuía campos `address`, `city` e `state` no banco e na API, mas o formulário não permitia informá-los. Isso causava a mensagem **Não informado** no cabeçalho do orçamento do Laboratório.

## O que mudou
- O formulário **Comercial → Cadastros → Empresas emitentes** agora disponibiliza **Endereço completo (rua, número, bairro, complemento)**, **Cidade** e **UF**.
- Ao selecionar uma emitente, os campos são carregados com os dados já gravados. Isso evita zerar nome, CNPJ e contatos ao alterar só o endereço.
- O resumo de cada emitente mostra seu endereço atual.
- O gerador de PDF compõe endereço e cidade/UF da empresa emissora vinculada à O.S.; endereços longos passam a ampliar o cabeçalho, evitando truncamentos.
- O tema claro e o escuro apresentam os novos controles com contraste adequado.

## Empresas e histórico
Cada empresa é identificada por seu código, já usado na O.S. A alteração da emitente A **não substitui** o endereço de B.

**Atenção ao histórico:** revisões de orçamento **já emitidas** guardam a fotografia dos dados da emitente da época da emissão, e por isso não serão reescritas. Novos orçamentos, rascunhos e novas revisões usarão o cadastro atualizado ao emitir.

Nenhum endereço verdadeiro foi inferido das informações presentes na imagem do usuário. Preencha os dados reais no cadastro.

## Como testar
1. Faça backup do banco e dos uploads, extraia a V40 em uma pasta nova e execute `INICIAR_SENTICO.cmd`.
2. Em **Comercial → Cadastros → Empresas emitentes**, selecione a empresa desejada.
3. Confira nome/CNPJ/telefone/e-mail carregados, informe endereço, cidade e UF e clique em **Salvar dados da emitente**.
4. Selecione uma segunda emitente, confirme que seus dados continuam independentes e salve outro endereço.
5. Abra uma O.S. de cada empresa, em **Laboratório → Orçamento**, e gere uma **prévia de rascunho**. Verifique a linha de endereço no cabeçalho.
6. Confirme que um PDF **já emitido** continua com o endereço histórico.
7. Confira ambos os temas no desktop e no celular.

## Arquivos alterados
- `codigo-fonte/apps/web/src/features/commercial/CommercialDashboard.tsx`
- `codigo-fonte/apps/web/src/features/commercial/commercial.css`
- `codigo-fonte/apps/web/src/shared/theme/light-theme.css`
- `codigo-fonte/apps/api/app/laboratory/quote_pdf.py`
- `codigo-fonte/apps/api/tests/test_v40_company_issuer_address.py` (novos testes)

## Validação
- 12 testes do cadastro/perfil/snapshot, aprovados.
- 23 testes direcionados do instalador, aprovados.
- 3 PDFs de ensaio com dados fictícios gerados sem erros, com endereços diferentes e um endereço longo; renderizados e conferidos.
- TSX com 0 erros sintáticos na verificação local.

A compilação integral React/Vite, o salvamento real no PostgreSQL e a homologação em Docker/Windows ainda precisam ser realizados localmente.

**Banco:** nenhuma migração adicional; nenhuma ação aplicada à VPS.
