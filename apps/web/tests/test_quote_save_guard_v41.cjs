/* Verificações reais do comparador de gravação, sem instalar React/Vite. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
// Use the native Node 22 TypeScript loader, just like the V42 test.
// TypeScript 7's CLI is not the legacy JavaScript compiler API.
async function main() {
  const { quoteNumber, quoteMoneyNumber, expectedQuoteTotal, verifyQuoteSaved } =
    await import('../src/features/laboratory/components/quoteSaveGuard.ts');
  let tests=0;
  function check(fn){ fn();tests++; }
  check(()=>assert.equal(quoteNumber('R$ 22.000,00'),22000));
  check(()=>assert.equal(quoteNumber('1500,00'),1500));
  check(()=>assert.equal(quoteNumber('1500.00'),1500));
  check(()=>assert.equal(quoteNumber('1.234,56'),1234.56));
  check(()=>assert.equal(quoteMoneyNumber('25.000'),25000));
  check(()=>assert.equal(quoteMoneyNumber('1.000'),1000));
  check(()=>assert.equal(quoteNumber('1.000'),1));
  const snapshot={service_code:'3312102 / 14.01',technical_report:'Laudo alterado',services_description:'Reparo',delivery_days:20,billing_days:21,billing_terms:'21 dias',warranty_months:3,warranty_terms:'3 meses',payment_terms:'PIX',validity_days:30,return_condition:'Retorno',consumer_clause:'CDC',supply_clause:'Prazo',estimate_clause:'Estimativa',discount_type:'none',discount_value:0,items:[{description:'Manutenção',quantity:2,unit_value:11000}],photos:[{document_id:8,caption:'Antes do reparo'}]};
  const saved={...snapshot,status:'draft',emitted_at:null,total:'22000.00',subtotal:'22000.00',items:[{description:'Manutenção',quantity:'2.000',unit_value:'11000.00'}],photos:[{document_id:8,caption:'Antes do reparo'}]};
  check(()=>assert.equal(expectedQuoteTotal(snapshot),2200000));
  check(()=>assert.equal(verifyQuoteSaved(snapshot,saved),null));
  check(()=>assert.match(verifyQuoteSaved(snapshot,{...saved,total:'25000.00'}),/total/i));
  check(()=>assert.match(verifyQuoteSaved(snapshot,{...saved,items:[{...saved.items[0],unit_value:'12500.00'}]}),/item/i));
  check(()=>assert.match(verifyQuoteSaved(snapshot,{...saved,technical_report:'Laudo antigo'}),/technical report/i));
  check(()=>assert.match(verifyQuoteSaved(snapshot,{...saved,photos:[]}),/fotos/i));
  check(()=>assert.match(verifyQuoteSaved(snapshot,{...saved,status:'emitted'}),/rascunho/i));
  check(()=>assert.match(verifyQuoteSaved(snapshot,{...saved,total:null}),/total/i));
  const editor = fs.readFileSync(path.join(__dirname,'../src/features/laboratory/components/QuoteEditor.tsx'),'utf8');
  check(()=>assert.match(editor,/const responseError = verifyQuoteSaved\(snapshot, result\)/));
  check(()=>assert.match(editor,/const persistedError = verifyQuoteSaved\(snapshot, savedQuote\)/));
  check(()=>{ const verify=editor.indexOf('const persistedError = verifyQuoteSaved(snapshot, savedQuote)'); const guard=editor.indexOf('if (persistedError)',verify); const reject=editor.indexOf('throw new Error(',guard); const select=editor.indexOf('selectQuote(savedQuote);',reject); assert.ok(verify>=0 && guard>verify && reject>guard && select>reject); });
  const detail = fs.readFileSync(path.join(__dirname,'../src/features/laboratory/LaboratoryDashboard.tsx'),'utf8');
  check(()=>assert.match(detail,/tab === "quote" \? "Salvar orçamento"/));
  check(()=>assert.match(detail,/quoteSaveRef\.current\?\.save\(\)/));
  console.log(`${tests} verificações V41 passaram: moeda brasileira, salvamento confirmado, falha preservada e botão geral integrado.`);
}
main().catch(error => { console.error(error); process.exitCode = 1; });
