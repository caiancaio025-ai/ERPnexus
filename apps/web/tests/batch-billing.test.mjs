import test from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

// Vite resolves extensionless TS imports; provide the same resolution for Node.
registerHooks({ resolve(specifier, context, nextResolve) {
  try { return nextResolve(specifier, context); }
  catch (error) {
    if (error.code === 'ERR_MODULE_NOT_FOUND' && specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier)) return nextResolve(`${specifier}.ts`, context);
    throw error;
  }
} });
const { billingDraft, billingTotal, validateBillingSelection, suggestedExitInvoice } = await import('../src/features/finance/batchBilling.ts');
const order = (id, extra = {}) => ({ id, number: `OS-${id}`, company_code: 'universo_eletronica', customer_id: 7, customer_name: 'Cliente', equipment_label: 'Inversor', status: 'approved', version: 3, approved_value: 100, total_registered: 20, remaining_to_issue: 80, ...extra });

test('billing starts from remaining amount and sums Brazilian values in cents', () => {
  const first = billingDraft(order(1)); const second = billingDraft(order(2));
  assert.equal(first.amount, '80,00');
  first.amount = '1.250,51'; second.amount = '0,29';
  assert.equal(billingTotal([first, second]), 1250.80);
  assert.equal(validateBillingSelection([first, second]), null);
});
test('joint billing checks customer IDs, company and duplicate IDs rather than displayed names', () => {
  const first = billingDraft(order(1));
  assert.match(validateBillingSelection([first, billingDraft(order(2, { customer_id: 8 }))]), /mesmo cadastro/);
  assert.match(validateBillingSelection([first, billingDraft(order(2, { customer_id: null }))]), /mesmo cadastro/);
  assert.match(validateBillingSelection([first, billingDraft(order(2, { company_code: 'universo_automacao' }))]), /mesma empresa/);
  assert.match(validateBillingSelection([first, first]), /duas vezes/);
});
test('billing keeps historical single-OS customerless records but refuses to group them', () => {
  assert.equal(validateBillingSelection([billingDraft(order(1, { customer_id: null }))]), null);
  assert.match(validateBillingSelection([billingDraft(order(1, { customer_id: null })), billingDraft(order(2, { customer_id: null }))]), /cadastro/);
});
test('parcel limits cannot create zero-cent entries or exceed 1000 resulting installments', () => {
  const first = billingDraft(order(1)); first.amount = '0,01';
  assert.match(validateBillingSelection([first], 2), /R\$ 0,01/);
  assert.equal(validateBillingSelection([first], 1), null);
  const rows = Array.from({ length: 50 }, (_, index) => billingDraft(order(index + 1)));
  assert.match(validateBillingSelection(rows, 21), /1.000/);
});
test('missing, malformed, negative and overprecision amounts are refused', () => {
  for (const amount of ['', 'abc', '-1', '1.2345']) {
    const row = billingDraft(order(1)); row.amount = amount;
    assert.match(validateBillingSelection([row]), /valor positivo/);
  }
});
test('exit invoice suggestion is explicit when invoice kinds have different numbers', () => {
  assert.equal(suggestedExitInvoice('123', ''), '123');
  assert.equal(suggestedExitInvoice('', '456'), '456');
  assert.equal(suggestedExitInvoice('123', '123'), '123');
  assert.equal(suggestedExitInvoice('123', '456'), '');
  assert.equal(suggestedExitInvoice('', ''), '');
});
