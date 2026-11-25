from playwright.sync_api import sync_playwright
from pathlib import Path
from PIL import Image
base=Path('/mnt/data/sentico_v22_work/codigo-fonte/apps/web/src')
files=['styles.css','features/dashboard/dashboard.css','features/notifications/notification-center.css','features/employees/employees.css','shared/theme/light-theme.css','shared/theme/light-semantic-colors.css','shared/theme/dark-elevated.css']
markup='''
<div class="dashboard-shell" style="display:block;min-height:100vh;padding:28px">
 <header class="dashboard-header"><div class="dashboard-heading"><span>PAINEL DE CONTROLE</span><h1>Bem-vindo ao Sêntico</h1><p>Visão consolidada das pendências e atividades.</p></div><div class="dashboard-tools"><button class="round-button">◎</button><button class="user-button"><span>Gestão</span></button></div></header>
 <div class="overview-grid">
   <div class="overview-card overview-card--danger"><div class="overview-card__top"><span class="overview-card__label">Orçamentos pendentes</span><span class="overview-card__icon">!</span></div><strong>12</strong><span class="overview-card__detail">Exigem atenção</span></div>
   <div class="overview-card overview-card--warning"><div class="overview-card__top"><span class="overview-card__label">Compras a receber</span><span class="overview-card__icon">▤</span></div><strong>08</strong><span class="overview-card__detail">Em andamento</span></div>
   <div class="overview-card overview-card--info"><div class="overview-card__top"><span class="overview-card__label">Equipamentos analisados</span><span class="overview-card__icon">✓</span></div><strong>24</strong><span class="overview-card__detail">Relatórios atualizados</span></div>
 </div>
 <section class="work-queue-section"><div class="work-queue-section__topline"><div><span class="section-kicker">LABORATÓRIO</span><h2>Pendências do dia</h2><p>Informações separadas conforme a função.</p></div></div>
 <div class="work-queue-grid"><article class="work-queue work-queue--warning"><div class="work-queue__header"><div class="work-queue__heading"><span class="work-queue__section">ORÇAMENTOS</span><h2>Equipamentos analisados</h2><p>Aguardando elaboração</p></div><strong class="work-queue__count">4</strong></div><div class="work-queue__rows"><button class="work-queue__item"><div class="work-queue__info"><strong>OS 39405 — CAPRICHE</strong><small>Inversor WEG CFW11</small></div><span class="work-queue__status">Analisado</span></button></div><button class="work-queue__footer">Ver todos →</button></article>
 <article class="work-queue work-queue--success"><div class="work-queue__header"><div class="work-queue__heading"><span class="work-queue__section">COMPRAS</span><h2>Material recebido</h2><p>Registro por usuário</p></div><strong class="work-queue__count">9</strong></div><div class="work-queue__rows"><button class="work-queue__item"><div class="work-queue__info"><strong>Solicitação 1024</strong><small>3 capacitores — Entregue</small></div><span class="work-queue__status">Recebido</span></button></div><button class="work-queue__footer">Abrir compras →</button></article></div></section>
 <section class="purchase-center" style="margin-top:24px"><div class="section-header"><div><span class="section-kicker">COMPRAS</span><h2>Central de eventos urgentes</h2><p>Atrasos e entregas previstas dos pedidos.</p></div><div class="event-filters"><button class="active">Todos</button><button>Atrasadas</button><button>Próximas</button></div></div><div class="purchase-events__empty" style="padding:25px;text-align:center">Nenhuma compra exige atenção neste filtro.</div></section>
 <section class="sentico-notifications" style="margin-top:22px;background:none"><div class="sentico-notifications__overview"><div class="sentico-notifications__overview-main"><span class="sentico-notifications__overview-icon">✦</span><div><span>Atividades recentes</span><strong>18</strong></div></div><button class="is-selected"><span>Não lidas</span><strong>6</strong><small>Requer atenção</small></button><button><span>Total</span><strong>58</strong><small>Histórico</small></button></div><div class="sentico-notifications__results"><div class="sentico-notifications__list"><div class="sentico-notifications__item is-unread" data-modulo="laboratorio"><div class="sentico-notifications__item-icon">✓</div><div class="sentico-notifications__item-body"><div class="sentico-notifications__item-top"><span class="sentico-notifications__module">Laboratório</span><span class="sentico-notifications__new">Novo</span></div><h3>OS 39405 — Analisado</h3><p>João concluiu a análise do inversor de frequência.</p></div></div><div class="sentico-notifications__item" data-modulo="compras"><div class="sentico-notifications__item-icon">▣</div><div class="sentico-notifications__item-body"><div class="sentico-notifications__item-top"><span class="sentico-notifications__module">Compras</span></div><h3>Material recebido</h3><p>Maria registrou a chegada dos materiais da OS 39405.</p></div></div></div></div></section>
</div>'''

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1320,'height':1100},device_scale_factor=1)
    for theme in ['escuro','claro']:
        page.set_content(markup)
        page.evaluate('theme => document.documentElement.setAttribute("data-sentico-theme",theme)',theme)
        for f in files: page.add_style_tag(content=(base/f).read_text(encoding='utf8'))
        page.wait_for_timeout(100)
        path=f'/mnt/data/sentico_v22_work/preview_{theme}_v22.png'
        page.screenshot(path=path,full_page=True)
        for css in ['.overview-card--danger','.event-filters button.active','.sentico-notifications__item.is-unread','.work-queue--warning']:
            print(theme,css,page.locator(css).evaluate('(el)=>({background:getComputedStyle(el).backgroundImage,color:getComputedStyle(el).color,border:getComputedStyle(el).borderTopColor})'))
        print('screenshot',path)
    browser.close()
