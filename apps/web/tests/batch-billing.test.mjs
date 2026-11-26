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
const { billingDraft, billingTotal, validateBillingSelection, suggestedExitInvoice, billingDocumentTotal, draftsFromSavedLinks, effectiveBillingRows, distributeBillingTotal, validateBillingAllocation, normalizeBillingConfirmation, billingDescription } = await import('../src/features/finance/batchBilling.ts');
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
test('one invoice permits zero-cent allocation cells while retaining a positive OS total and at most 1000 cells', () => {
  const first = billingDraft(order(1)); first.amount = '0,01';
  assert.equal(validateBillingSelection([first], 2), null);
  assert.equal(validateBillingSelection([first], 1), null);
  const rows = Array.from({ length: 50 }, (_, index) => billingDraft(order(index + 1)));
  assert.match(validateBillingSelection(rows, 21), /1.000/);
});
test('editing one installment uses the full invoice allocation and preserves other installments', () => {
  const entry = { id: 8, amount: '33.34', obligation_id: 7, obligation_total_amount: '100.00',
    work_orders: [{ work_order_id: 1, work_order_number: 'OS-1', amount: '16.67', version: 3 }],
    obligation_work_orders: [{ work_order_id: 1, work_order_number: 'OS-1', amount: '50.00', version: 3 }, { work_order_id: 2, work_order_number: 'OS-2', amount: '50.00', version: 3 }] };
  assert.equal(billingDocumentTotal(entry, '33,34'), 100);
  assert.equal(billingDocumentTotal(entry, '43,34'), 110);
  assert.deepEqual(draftsFromSavedLinks(entry).map(row => row.amount), ['50,00', '50,00']);
  assert.equal(billingDocumentTotal(null, '200,51'), 200.51);
});
test('allocations require the existing document total and equal division conserves every cent', () => {
  const rows = [billingDraft(order(1)), billingDraft(order(2)), billingDraft(order(3))];
  const result = distributeBillingTotal(rows, 100);
  assert.deepEqual(result.map(row => row.amount), ['33,34', '33,33', '33,33']);
  assert.equal(billingTotal(result), 100);
  assert.equal(validateBillingAllocation(result, 100, 3), null);
  assert.match(validateBillingAllocation(result, 200), /total do faturamento/);
  assert.equal(effectiveBillingRows([rows[0]], 240.11)[0].amount, '240,11');
  assert.equal(validateBillingAllocation([], 100), null, 'removing all links keeps an unlinked invoice');
  assert.throws(() => distributeBillingTotal(rows, .02), /R\$ 0,01/);
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
test('nullable historical checklist fields become empty controls without losing true confirmations', () => {
  const result = normalizeBillingConfirmation({ notes: null, purchase_order_number: null, service_report_confirmed: true, portal_submitted: null });
  assert.equal(result.notes, '');
  assert.equal(result.purchase_order_number, '');
  assert.equal(result.service_report_confirmed, true);
  assert.equal(result.portal_submitted, false);
});
test('automatic description fits the API limit even with 50 OS', () => {
  const rows = Array.from({ length: 50 }, (_, index) => billingDraft(order(index + 10000)));
  assert.equal(billingDescription(rows), 'Serviços de laboratório — 50 ordens de serviço');
  assert.ok(billingDescription(rows).length <= 180);
  assert.equal(billingDescription(rows.slice(0, 2)), 'Serviços de laboratório — OS-10000, OS-10001');
});
