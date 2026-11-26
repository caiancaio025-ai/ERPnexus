import test from 'node:test';
import assert from 'node:assert/strict';
import { quoteLineCents, quoteDiscountCents } from '../src/features/laboratory/components/groupedQuoteMoney.ts';

test('grouped quote rounds each fractional line HALF_UP before adding rows', () => {
  assert.equal(quoteLineCents(.5, .01), 1);
  assert.equal(quoteLineCents(.5, .01) + quoteLineCents(.5, .01), 2);
  assert.equal(quoteLineCents(.29, .50), 15);
  assert.equal(quoteLineCents(1.005, 10), 1005);
});
test('grouped quote percent and amount discounts use rounded cents', () => {
  assert.equal(quoteDiscountCents(1, 'percent', 50), 1);
  assert.equal(quoteDiscountCents(149, 'percent', 2.5), 4);
  assert.equal(quoteDiscountCents(20000, 'amount', 1.25), 125);
  assert.equal(quoteDiscountCents(20000, 'none', 1.25), 0);
});
