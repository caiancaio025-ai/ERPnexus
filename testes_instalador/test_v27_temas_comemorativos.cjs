const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
const root = path.resolve(__dirname, '../apps/web/src');
const store = new Map();
const rootAttrs = {};
const listeners = new Map();
const fakeWindow = {
  localStorage: {getItem: k => store.has(k) ? store.get(k) : null, setItem: (k,v) => store.set(k,v)},
  addEventListener: (k,fn) => listeners.set(k,fn),
  dispatchEvent: () => {},
  setInterval: () => 1,
};
const fakeDocument = {
  documentElement: {dataset: rootAttrs},
  hidden: false,
  addEventListener: () => {},
};
class FakeCustomEvent { constructor(type, init) {this.type=type; this.detail=init.detail;} }
globalThis.window = fakeWindow;
globalThis.document = fakeDocument;
globalThis.CustomEvent = FakeCustomEvent;
const mod = await import('../apps/web/src/shared/theme/seasonal.ts');
let testes = 0;
function verificar(nome, fn) {fn(); testes++; console.log(`PASS ${nome}`);}
const d = (year, month, day=17) => new Date(year, month-1, day, 12);
verificar('Páscoa 2026 5 abril', () => assert.equal(JSON.stringify(mod.dataPascoa(2026)), JSON.stringify({mes:4,dia:5})));
verificar('Páscoa 2027 28 março', () => assert.equal(JSON.stringify(mod.dataPascoa(2027)), JSON.stringify({mes:3,dia:28})));
verificar('Páscoa 2024 31 março', () => assert.equal(JSON.stringify(mod.dataPascoa(2024)), JSON.stringify({mes:3,dia:31})));
verificar('Carnaval em fevereiro', () => assert.equal(mod.temporadaNaData(d(2026,2)), 'carnaval'));
verificar('Páscoa em abril 2026', () => assert.equal(mod.temporadaNaData(d(2026,4)), 'pascoa'));
verificar('Páscoa em março 2027', () => assert.equal(mod.temporadaNaData(d(2027,3)), 'pascoa'));
verificar('São João em junho', () => assert.equal(mod.temporadaNaData(d(2026,6)), 'junho'));
verificar('Halloween em outubro', () => assert.equal(mod.temporadaNaData(d(2026,10)), 'halloween'));
verificar('Natal em dezembro', () => assert.equal(mod.temporadaNaData(d(2026,12)), 'natal'));
verificar('Natal também em novembro', () => assert.equal(mod.temporadaNaData(d(2026,11)), 'natal'));
verificar('Ano-Novo em janeiro', () => assert.equal(mod.temporadaNaData(d(2027,1)), 'ano_novo'));
verificar('Prévia Natal fora de época', () => assert.equal(mod.temporadaEfetiva({escolha:'natal',animacoes:true},d(2026,11)), 'natal'));
verificar('Preferência desligada', () => assert.equal(mod.temporadaEfetiva({escolha:'desativado',animacoes:true},d(2026,12)), null));
verificar('Preferência padrão automática', () => assert.equal(JSON.stringify(mod.lerConfigTemporada()), JSON.stringify({escolha:'automatico',animacoes:true})));
verificar('Persistência das escolhas e animações', () => {mod.salvarConfigTemporada({escolha:'junho',animacoes:false});assert.equal(mod.lerConfigTemporada().escolha,'junho'); assert.equal(mod.lerConfigTemporada().animacoes,false);assert.equal(rootAttrs.senticoTemporada,'junho');assert.equal(rootAttrs.senticoAnimacoes,'desligadas');});
verificar('Desativado remove a decoração', () => {mod.salvarConfigTemporada({escolha:'desativado',animacoes:false});assert.equal(rootAttrs.senticoTemporada,undefined);});
verificar('Configuração inválida é ignorada', () => {store.set('sentico:temporada:v1', '{"escolha":"hack","animacoes":true}');assert.equal(mod.lerConfigTemporada().escolha, 'automatico');});
verificar('Regras de acessibilidade e impressão presentes', () => {const css=fs.readFileSync(path.join(root,'shared/theme/seasonal.css'),'utf8');assert.match(css,/prefers-reduced-motion:reduce/);assert.match(css,/@media print/);assert.match(css,/pointer-events:none/);});
verificar('CSS decorativo sem regras destrutivas', () => {const css=fs.readFileSync(path.join(root,'shared/theme/seasonal.css'),'utf8');assert.doesNotMatch(css,/display\s*:\s*none\s*!important[^}]*\.lab-/);});
console.log(`\nTOTAL: ${testes} testes aprovados.`);

})().catch((error) => { console.error(error); process.exitCode = 1; });
