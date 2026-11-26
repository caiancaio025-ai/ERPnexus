import test from 'node:test';
import assert from 'node:assert/strict';
import { materialRequestSaveMatches } from '../src/features/purchasing/materialRequestSave.ts';

const payload = () => ({ status: 'received', unit_cost: 12.5, note: null, inventory_destination: 'new', inventory_name: 'Ventilador', inventory_mode: 'serialized', inventory_serial: null, inventory_category: 'componentes', inventory_item_id: null, inventory_format_id: null, inventory_details: { slot_id: 7, subtype_id: null, manufacturer: 'Marca', model: '120 mm', unit: 'UN', notes: 'Peça de reposição' } });

test('acknowledges a lost receipt response only when persisted destination and item details match', () => {
  const expected = payload();
  assert.equal(materialRequestSaveMatches(expected, { ...expected, id: 9, unit_cost: '12.50', updated_at: '2026-11-26T18:00:00Z' }), true);
  for (const patch of [{ status: 'purchased' }, { inventory_name: 'Outro item' }, { unit_cost: '14.50' }, { inventory_mode: 'bulk' }, { inventory_details: { ...expected.inventory_details, slot_id: 8 } }, { inventory_details: { ...expected.inventory_details, notes: 'Alteração de outra pessoa' } }]) {
    assert.equal(materialRequestSaveMatches(expected, { ...expected, ...patch }), false);
  }
});
test('existing item receipt can adopt its canonical name but cannot acknowledge a different stock target', () => {
  const expected = { status: 'received', inventory_destination: 'existing', inventory_item_id: 42, inventory_name: null };
  assert.equal(materialRequestSaveMatches(expected, { ...expected, inventory_name: 'Nome do cadastro' }), true);
  assert.equal(materialRequestSaveMatches(expected, { ...expected, inventory_item_id: 43 }), false);
});
test('a request snapshot cannot prove delivery of a separate audit note', () => {
  const expected = { ...payload(), note: 'Registrar conferência de chegada' };
  assert.equal(materialRequestSaveMatches(expected, expected), false);
});
