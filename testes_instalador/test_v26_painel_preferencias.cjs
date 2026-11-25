/* Testes locais de regras de visibilidade (sem API, React ou dados de produção). */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
const {
  availableDashboardAreas, alertDashboardArea, dashboardPreferenceKey,
  readHiddenDashboardAreas, serializeHiddenDashboardAreas,
} = await import('../apps/web/src/features/dashboard/dashboardPreferences.ts');
let tests = 0;
function check(name, fn) { fn(); tests++; console.log('OK:', name); }
const makeSummary = (audience, sections, alertKeys = [], actions = []) => ({
  audience, work_queues: sections.map(section => ({ section })),
  alerts: alertKeys.map(key => ({ key })), purchase_events: [], quick_actions: actions,
  monthly_equipment_entries: { month_label: 'novembro de 2026', count: 27 },
});
check('Gestão oferece somente os setores recebidos da API', () => {
  const list = availableDashboardAreas(makeSummary('gestao', ['laboratorio','orcamentos','compras','financeiro','estoque'], ['unread_notifications'],[{key:'new_work_order'}]));
  assert.deepEqual(list,['laboratorio','orcamentos','compras','financeiro','estoque','notificacoes','atalhos']);
});
check('Laboratório não oferece Financeiro ou Compras', () => {
  const list = availableDashboardAreas(makeSummary('lab',['laboratorio'],['lab_entries'],[{key:'new_work_order'}]));
  assert.deepEqual(list,['laboratorio','notificacoes','atalhos']);
});
check('ADM não recebe setores restritos', () => {
  const list = availableDashboardAreas(makeSummary('admin',['orcamentos'],['quotes_pending'],[{key:'new_budget'}]));
  assert.deepEqual(list,['orcamentos','notificacoes','atalhos']);
});
check('Compras sem eventos ainda pode exibir sua central', () => {
  assert.deepEqual(availableDashboardAreas(makeSummary('compras',[],[])),['compras','notificacoes']);
});
check('Armazenamento diferencia IDs de usuário', () => {
  assert.notEqual(dashboardPreferenceKey(1),dashboardPreferenceKey(2));
});
check('Nova conta começa com todas as opções visíveis', () => {
  assert.deepEqual(readHiddenDashboardAreas(null),[]);
});
check('Preferências são persistidas e restauradas sem perder ordem', () => {
  const json=serializeHiddenDashboardAreas(['financeiro','laboratorio']);
  assert.deepEqual(readHiddenDashboardAreas(json),['laboratorio','financeiro']);
});
check('Dados corrompidos não impedem carregamento', () => {
  assert.deepEqual(readHiddenDashboardAreas('{erro'),[]);
});
check('Setores desconhecidos no armazenamento são ignorados', () => {
  assert.deepEqual(readHiddenDashboardAreas('{"hidden":["financeiro","admin","estoque"]}'),['financeiro','estoque']);
});
check('Alertas são classificados no setor correspondente', () => {
  assert.equal(alertDashboardArea('quotes_pending'),'orcamentos');
  assert.equal(alertDashboardArea('finance_overdue'),'financeiro');
  assert.equal(alertDashboardArea('delayed_purchases'),'compras');
  assert.equal(alertDashboardArea('lab_entries'),'laboratorio');
  assert.equal(alertDashboardArea('unread_notifications'),'notificacoes');
});
check('Indicadores novos não somem sem escolha do usuário', () => {
  assert.equal(alertDashboardArea('future_alert'),'geral');
});
console.log(`APROVADOS: ${tests} testes de preferências do painel`);

})().catch((error) => { console.error(error); process.exitCode = 1; });
