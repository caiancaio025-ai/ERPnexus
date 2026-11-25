import test from 'node:test';
import assert from 'node:assert/strict';
import { buildApiUrl, fetchJson, TransportError } from '../src/shared/api/requestPolicy.ts';
import { changedFields, conflictingFields, saveVersionedChanges, ConcurrentEditError } from '../src/shared/api/editChanges.ts';
import { moneyInput, optionalMoneyInput } from '../src/shared/forms/moneyInput.ts';

const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json', 'x-request-id': 'test-request-48' } });

test('API URL uses a single API prefix with relative and absolute installations', () => {
  assert.equal(buildApiUrl('/api/auth/me', '/api'), '/api/auth/me');
  assert.equal(buildApiUrl('/auth/me', '/api'), '/api/auth/me');
  assert.equal(buildApiUrl('/api/auth/me', 'https://example.test/api/'), 'https://example.test/api/auth/me');
  assert.equal(buildApiUrl('/api/auth/me', 'https://example.test/v1'), 'https://example.test/v1/auth/me');
  assert.equal(buildApiUrl('https://other.test/api/me'), 'https://other.test/api/me');
});

test('GET retries a temporary proxy failure and returns the recovered JSON', async (t) => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => ++calls === 1 ? new Response('temporarily unavailable', { status: 503 }) : json({ saved: true }));
  const result = await fetchJson('/api/list', {}, { retryDelayMs: 0 });
  assert.equal(calls, 2);
  assert.deepEqual(result.payload, { saved: true });
});

test('GET retries a disconnected read once, with bounded attempts', async (t) => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls += 1; throw new TypeError('offline'); });
  await assert.rejects(fetchJson('/api/list'), (cause) => cause instanceof TransportError && cause.kind === 'network');
  assert.equal(calls, 2);
});

test('POST never automatically repeats an acknowledged or ambiguous write', async (t) => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls += 1; return json({ detail: 'busy' }, 503); });
  assert.equal((await fetchJson('/api/purchasing/orders', { method: 'POST', body: '{}' }, { retries: 2 })).response.status, 503);
  assert.equal(calls, 1);
  t.mock.method(globalThis, 'fetch', async () => { calls += 1; throw new TypeError('response lost after commit'); });
  await assert.rejects(fetchJson('/api/purchasing/orders', { method: 'POST' }), /Consulte o registro antes de enviar novamente/);
  assert.equal(calls, 2);
});

test('DELETE is not replayed after a timeout and the timer aborts the request', async (t) => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    calls += 1;
    return new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true }));
  });
  await assert.rejects(fetchJson('/api/item/1', { method: 'DELETE' }, { timeoutMs: 5 }), (cause) => cause.kind === 'timeout');
  assert.equal(calls, 1);
});

test('caller cancellation is propagated without retrying or masquerading as a network fault', async (t) => {
  const controller = new AbortController();
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    calls += 1;
    return new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true }));
  });
  const request = fetchJson('/api/list', { signal: controller.signal });
  controller.abort(new DOMException('cancelled', 'AbortError'));
  await assert.rejects(request, { name: 'AbortError' });
  assert.equal(calls, 1);
});

test('successful HTML or malformed JSON is rejected instead of reported as saved', async (t) => {
  for (const response of [new Response('<html>login</html>', { headers: { 'content-type': 'text/html' } }), new Response('{truncated', { headers: { 'content-type': 'application/json', 'x-request-id': 'trace-48' } })]) {
    t.mock.method(globalThis, 'fetch', async () => response);
    await assert.rejects(fetchJson('/api/order', { method: 'PATCH' }), (cause) => cause.kind === 'invalid_response');
  }
});

test('204 deletion and JSON validation errors retain their exact semantics', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(null, { status: 204 }));
  assert.equal((await fetchJson('/api/item/1', { method: 'DELETE' })).payload, undefined);
  t.mock.method(globalThis, 'fetch', async () => json({ detail: [{ loc: ['body', 'amount'], msg: 'invalid amount' }] }, 422));
  const result = await fetchJson('/api/order', { method: 'PATCH' });
  assert.equal(result.response.status, 422);
  assert.equal(result.response.headers.get('x-request-id'), 'test-request-48');
  assert.equal(result.payload.detail[0].loc[1], 'amount');
});

test('purchase and OS monetary fields accept Brazilian and API decimal values', () => {
  assert.equal(moneyInput('1.250,50'), 1250.5);
  assert.equal(moneyInput('1250.50'), 1250.5);
  assert.equal(moneyInput('R$ 1.250,50'), 1250.5);
  assert.equal(moneyInput('22.000'), 22000);
  assert.equal(moneyInput('0,50'), 0.5);
  assert.equal(optionalMoneyInput(''), null);
  assert.equal(optionalMoneyInput('1.250,50'), '1250.5');
  assert.equal(optionalMoneyInput('incompleto'), 'incompleto');
  assert.ok(Number.isNaN(moneyInput('abc')));
});

test('OS sends only changed fields and preserves an explicit clearing', () => {
  const baseline = { model: 'CFW700', notes: 'old', approved_value: '100.00', customer_id: 7 };
  const current = { ...baseline, notes: null };
  assert.deepEqual(changedFields(baseline, current), { notes: null });
  assert.deepEqual(conflictingFields(baseline, current, { ...baseline, approved_value: '150.00' }), []);
});

test('version conflict from quote/stock can safely rebase an unrelated OS edit once', async () => {
  let server = { version: 2, model: 'CFW700', notes: 'old', approved_value: '200.00' };
  const baseline = { model: 'CFW700', notes: 'old', approved_value: '100.00' };
  const current = { ...baseline, notes: 'new notes' };
  const writes = [];
  const result = await saveVersionedChanges(baseline, current, 1, {
    save: async (patch, version) => {
      writes.push({ patch, version });
      if (version !== server.version) throw { status: 409 };
      server = { ...server, ...patch, version: version + 1 };
      return server;
    },
    read: async () => server,
    snapshot: ({ version, ...data }) => data,
  });
  assert.deepEqual(writes, [{ patch: { notes: 'new notes' }, version: 1 }, { patch: { notes: 'new notes' }, version: 2 }]);
  assert.equal(result.approved_value, '200.00');
  assert.equal(result.notes, 'new notes');
  assert.equal(result.version, 3);
});

test('concurrent modification of the same field blocks overwrite and keeps the local draft', async () => {
  const baseline = { notes: 'old', approved_value: '100' };
  const current = { ...baseline, notes: 'my draft' };
  let calls = 0;
  await assert.rejects(saveVersionedChanges(baseline, current, 1, {
    save: async () => { calls += 1; throw { status: 409 }; },
    read: async () => ({ version: 2, notes: 'colleague draft', approved_value: '100' }),
    snapshot: ({ version, ...data }) => data,
  }), (cause) => cause instanceof ConcurrentEditError && cause.fields[0] === 'notes');
  assert.equal(calls, 1);
  assert.equal(current.notes, 'my draft');
});

test('ambiguous write failures never trigger version rebase or a second mutation', async () => {
  let calls = 0, reads = 0;
  await assert.rejects(saveVersionedChanges({ notes: 'old' }, { notes: 'new' }, 1, {
    save: async () => { calls += 1; throw new Error('response lost'); },
    read: async () => { reads += 1; return { version: 2, notes: 'new' }; },
    snapshot: ({ version, ...data }) => data,
  }), /response lost/);
  assert.equal(calls, 1);
  assert.equal(reads, 0);
});
