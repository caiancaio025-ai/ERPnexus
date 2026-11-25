const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../apps/web');
const src=path.join(root,'src');
const get=(p)=>fs.readFileSync(path.join(src,p),'utf8');
let n=0;const check=(name,fn)=>{fn();n++;console.log('PASS '+name);};
const decor=get('shared/theme/SeasonalDecorations.tsx');
const banner=get('shared/theme/SeasonalDashboardBanner.tsx');
const season=get('shared/theme/seasonal.ts');
const css=get('shared/theme/seasonal.css');
const dashboard=get('features/dashboard/Dashboard.tsx');
check('Painel importa e renderiza componente real do tema',()=>{
  assert.match(dashboard,/import \{ SeasonalDashboardBanner \}/);
  assert.match(dashboard,/<SeasonalDashboardBanner \/>/);
});
check('Halloween com abóboras, caveiras, doces, teias e morcegos',()=>{
  for(const s of ['🎃','💀','🍬','🍭','🕸️','🦇']) assert.ok(decor.includes(s),s);
});
check('Carnaval com sombrinhas, máscaras, confetes e fitas',()=>{
  for(const s of ['🎭','☂️','__confetti','__fitas']) assert.ok(decor.includes(s),s);
});
check('Ano-Novo com fogos, champanhe e saudação dinâmica',()=>{
  for(const s of ['__fireworks','__burst','🍾','🥂']) assert.ok(decor.includes(s),s);
  assert.match(banner,/Feliz \$\{ano\}!/);
});
check('Seis artes reais de decoração disponíveis no frontend',()=>{
  for(const slug of ['natal','ano_novo','carnaval','pascoa','junho','halloween']){
    const f=path.join(root,'public/temas-comemorativos',`${slug}.webp`);
    assert.ok(fs.statSync(f).size>10000,f);
  }
});
check('Preferências por navegador seguem válidas',()=>{
  assert.match(season,/const CHAVE = "sentico:temporada:v1"/);
  assert.match(season,/salvarConfigTemporada/);
  assert.match(decor,/EVENTO_TEMPORADA/);
  assert.match(banner,/EVENTO_TEMPORADA/);
});
check('Datas de Natal em novembro-dezembro, janeiro de Ano-Novo',()=>{
  assert.match(season,/mes === 11 \|\| mes === 12/);
  assert.match(season,/mes === 1\) return "ano_novo"/);
});
check('Decoração é não interativa, e oculta na impressão',()=>{
  assert.match(css,/\.sentico-festas \{[^}]*pointer-events:none/);
  assert.match(css,/@media print/);
});
check('Acessibilidade: respeita movimento reduzido e desligamento de animações',()=>{
  assert.match(css,/prefers-reduced-motion:reduce/);
  assert.match(css,/data-sentico-animacoes="desligadas"/);
});
check('Responsividade em celular',()=>{
  assert.match(css,/@media \(max-width:760px\)/);
  assert.match(css,/\.sentico-banner-festa__arte \{width:55%/);
});
check('Dashboard não usa screenshot integral no lugar dos dados',()=>{
  assert.match(dashboard,/summary\.monthly_equipment_entries/);
  assert.match(dashboard,/apiClient/);
  assert.doesNotMatch(banner,/dashboard_sêntico/);
});
console.log(`\n${n} testes V29 aprovados`);
