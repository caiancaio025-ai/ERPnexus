import test from 'node:test';
import assert from 'node:assert/strict';
import { groupedQuoteContentMatches } from '../src/features/laboratory/components/groupedQuoteSave.ts';

const snapshot = () => ({ version: 2, work_order_ids: [1, 2], title: 'Conjunto', service_code: '14.01', technical_report: 'Laudo', services_description: 'Reparo', delivery_days: 20, billing_days: 21, billing_terms: '21 dias', warranty_months: 3, warranty_terms: '3 meses', payment_terms: 'PIX', validity_days: 30, return_condition: 'Devolução', consumer_clause: 'A', supply_clause: 'B', estimate_clause: 'C', discount_type: 'amount', discount_value: 10, items: [{work_order_id: 1, description: 'Reparo A', quantity: 1, unit_value: 100}, {work_order_id: 2, description: 'Reparo B', quantity: 2, unit_value: 50}] });

test('lost PUT acknowledgement recognizes matching persisted content despite server IDs and decimals', () => {
  const expected = snapshot();
  const record = { ...expected, id: 8, version: 3, discount_value: '10.00', work_order_ids: [2, 1], items: expected.items.map((item, index) => ({ ...item, id: index + 20, position: index + 1, quantity: String(item.quantity), unit_value: Number(item.unit_value).toFixed(2) })) };
  assert.equal(groupedQuoteContentMatches(expected, record), true);
});
test('reconciliation refuses to replace local changes with different concurrent content', () => {
  const expected = snapshot();
  assert.equal(groupedQuoteContentMatches(expected, { ...expected, technical_report: 'Laudo de outro operador' }), false);
  assert.equal(groupedQuoteContentMatches(expected, { ...expected, items: expected.items.map((item, index) => index ? { ...item, unit_value: 55 } : item) }), false);
  assert.equal(groupedQuoteContentMatches(expected, { ...expected, work_order_ids: [1, 3] }), false);
  assert.equal(groupedQuoteContentMatches(expected, { ...expected, items: expected.items.slice(0, 1) }), false);
});
