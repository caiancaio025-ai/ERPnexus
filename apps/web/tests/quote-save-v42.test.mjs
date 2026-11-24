import test from 'node:test';
import assert from 'node:assert/strict';
import {
  quoteMoneyNumber, quoteNumber, expectedQuoteSubtotal, expectedQuoteTotal, verifyQuoteSaved,
} from '../src/features/laboratory/components/quoteSaveGuard.ts';

const payload = (unitValue='22000.00', quantity=1) => ({
  service_code:'3312102 / 14.01', technical_report:'Laudo', services_description:'Serviço',
  billing_terms:'21 dias', warranty_terms:'3 meses',payment_terms:'PIX',
  return_condition:'Retorno',consumer_clause:'CDC',supply_clause:'Prazo',estimate_clause:'Estimativa',
  delivery_days:20,billing_days:21,warranty_months:3,validity_days:30,
  discount_type:'none', discount_value:0,
  items:[{description:'Serviço', quantity, unit_value:quoteMoneyNumber(unitValue)}],photos:[],
});
const saved=(p, total='22000.00')=>({
  ...p, id:200, work_order_id:30740,revision:2,status:'draft',emitted_at:null,
  total, subtotal:total,
  items:p.items.map((item,index)=>({id:4+index,position:index+1,description:item.description,quantity:item.quantity.toFixed(3),unit_value:item.unit_value.toFixed(2)})),
});

test('converte números digitados em pt-BR e valores monetários da API',()=>{
  assert.equal(quoteMoneyNumber('22.000,00'),22000);
  assert.equal(quoteMoneyNumber('22000.00'),22000);
  assert.equal(quoteMoneyNumber('8.500'),8500);
  assert.equal(quoteNumber('2,000'),2);
});
test('salva R02 de R$ 22.000 e mantém quantidades e total da revisão',()=>{
  const p=payload();
  assert.equal(expectedQuoteTotal(p),2200000);
  assert.equal(verifyQuoteSaved(p,saved(p)),null);
});
test('detecta retorno antigo com valores concretos para diagnóstico',()=>{
  const p=payload();
  const message=verifyQuoteSaved(p,saved(p,'8500.00'));
  assert.match(message,/solicitado R\$\s+22\.000,00/);
  assert.match(message,/registrado R\$\s+8\.500,00/);
});
test('quantidade 2 × R$ 1.500 = R$ 3.000',()=>{
  const p=payload('1.500,00',2);
  assert.equal(expectedQuoteSubtotal(p),300000);
  assert.equal(expectedQuoteTotal(p),300000);
  assert.equal(verifyQuoteSaved(p,saved(p,'3000.00')),null);
});
test('arredondamento de quantidade em 3 casas coincide com NUMERIC em centavos',()=>{
  const p=payload('0.50',1.333);
  assert.equal(expectedQuoteSubtotal(p),67);
  assert.equal(expectedQuoteTotal(p),67);
  assert.equal(verifyQuoteSaved(p,saved(p,'0.67')),null);
});
