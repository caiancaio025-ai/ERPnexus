import test from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

registerHooks({ resolve(specifier, context, nextResolve) {
  try { return nextResolve(specifier, context); }
  catch (error) {
    if (error.code === 'ERR_MODULE_NOT_FOUND' && specifier.startsWith('.') && !/\.[a-z]+$/i.test(specifier)) return nextResolve(`${specifier}.ts`, context);
    throw error;
  }
} });
const { ApiError } = await import('../src/shared/api/apiError.ts');
const { billingDraftSnapshot, billingLinkSnapshot, financialUpdateMatches, persistFinancialUpdate } = await import('../src/features/finance/financialEntrySave.ts');
const links = [{ work_order_id: 1, amount: '40.00', version: 5, exit_invoice: '123', billing_confirmation: { notes: 'Conferido' } }, { work_order_id: 2, amount: '60.00', version: 7, exit_invoice_2: '123' }];
const saved = { id: 1, version: 2, amount: '100.00', description: 'Reparo', notes: null, work_orders: links };
const payload = { version: 1, amount: 100, description: 'Reparo', notes: '', exit_invoice: '123', work_orders: [{ work_order_id: 2, amount: 60, version: 3 }, { work_order_id: 1, amount: 40, version: 4, billing_confirmation: { notes: 'Conferido' } }] };

test('financial reconciliation compares allocation and checklist intent, excluding incremented versions', () => {
  assert.equal(financialUpdateMatches(saved, payload), true);
  assert.equal(financialUpdateMatches({ ...saved, amount: '100.01' }, payload), false);
  assert.equal(financialUpdateMatches({ ...saved, work_orders: [{ ...links[0], amount: '50.00' }, { ...links[1], amount: '50.00' }] }, payload), false);
  assert.equal(financialUpdateMatches({ ...saved, work_orders: [{ ...links[0], billing_confirmation: { notes: 'Outro' } }, links[1]] }, payload), false);
  assert.equal(financialUpdateMatches({ ...saved, work_orders: [links[0], { ...links[1], exit_invoice_2: null }] }, payload), false);
  assert.equal(billingDraftSnapshot([{ order: { id: 1 }, amount: '40.00', confirmation: { notes: 'Conferido' } }]), billingLinkSnapshot([links[0]]));
});
test('installment reconciliation uses obligation allocation, not the selected installment share', () => {
  const entry = { ...saved, obligation_id: 9, obligation_total_amount: '100.00', amount: '25.00', obligation_work_orders: links, work_orders: links.map(link => ({ ...link, amount: String(Number(link.amount) / 4) })) };
  assert.equal(financialUpdateMatches(entry, { ...payload, amount: 25, obligation_total_amount: 100 }), true);
  assert.equal(financialUpdateMatches(entry, { ...payload, amount: 25, obligation_total_amount: 101 }), false);
});
test('lost PUT acknowledgement is confirmed by a read without a second financial write', async () => {
  let writes = 0, reads = 0;
  const result = await persistFinancialUpdate(payload, async () => { writes++; throw new ApiError('Conexão interrompida', 0); }, async () => { reads++; return saved; });
  assert.equal(result, saved);
  assert.equal(writes, 1); assert.equal(reads, 1);
});
test('conflicting content and failed confirmation preserve the original conflict and version', async () => {
  const conflict = new ApiError('Versão alterada por outra operação.', 409);
  for (const read of [async () => ({ ...saved, description: 'Alterado por outro usuário' }), async () => { throw new Error('Read unavailable'); }]) {
    let writes = 0;
    await assert.rejects(persistFinancialUpdate(payload, async () => { writes++; throw conflict; }, read), error => error === conflict);
    assert.equal(writes, 1);
  }
  let reads = 0;
  const invalid = new ApiError('Rateio inválido', 422);
  await assert.rejects(persistFinancialUpdate(payload, async () => { throw invalid; }, async () => { reads++; return saved; }), error => error === invalid);
  assert.equal(reads, 0);
  assert.equal(payload.version, 1);
});
