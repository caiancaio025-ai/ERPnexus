from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT


def test_aplicativo_instalado_no_windows_recebe_web_push():
    toggle = (CODE / 'apps/web/src/shared/ui/PushNotificationsToggle.tsx').read_text()
    sw = (CODE / 'apps/web/public/sentico-sw.js').read_text()
    assert 'isDesktopDevice()' in toggle
    assert 'Ativar notificações neste ${device}' in toggle
    assert 'navigator.serviceWorker.register("/sentico-sw.js"' in toggle
    assert 'pushManager.subscribe' in toggle
    assert 'notificationclick' in sw
    assert 'clients.openWindow(url)' in sw
    assert 'showNotification(title' in sw


def test_compartilhamento_de_maquina_revoga_subscricao_no_logout():
    app = (CODE / 'apps/web/src/app/App.tsx').read_text()
    client = (CODE / 'apps/web/src/shared/notifications/pushClient.ts').read_text()
    assert 'await revokeDevicePush().catch' in app
    assert 'apiClient.post("/notifications/push/unsubscribe"' in client
    assert 'await subscription.unsubscribe()' in client


def test_migracao_instalador_reconhece_v18_e_preserva_revisao_anterior():
    installer = (ROOT / 'INSTALAR_SENTICO.ps1').read_text(encoding='utf-8-sig')
    assert "'20261112_01','20261116_01'" in installer
    assert "$escolha.Revisao -ne '20261126_04'" in installer
    assert "-notmatch '20261126_04'" in installer
    for f in ('catalogar_bancos_existentes.sh', 'inspecionar_arquivo_pgdata.sh'):
        s = (ROOT / 'scripts_recuperacao' / f).read_text()
        assert '20261112_01|20261116_01|20261117_01|20261123_01|20261123_02|20261126_01|20261126_02|20261126_03|20261126_04' in s


def test_experiencia_mobile_isolada_do_desktop():
    mobile = (CODE / 'apps/web/src/mobile-experience.css').read_text()
    assert '@media (max-width: 767px)' in mobile
    assert 'font-size: 16px' in mobile
    assert 'max-height: calc(100dvh - 16px)' in mobile
    assert 'import "./mobile-experience.css"' in (CODE / 'apps/web/src/main.tsx').read_text()


def test_payload_push_nao_revela_dados_na_tela_bloqueada():
    push = (CODE / 'apps/api/app/notifications/push.py').read_text()
    worker = (CODE / 'apps/web/public/sentico-sw.js').read_text()
    assert '"title": "SÊNTICO ERP · Nova atualização"' in push
    assert '"body": "Toque para consultar os detalhes no SÊNTICO."' in push
    assert 'const title = "SÊNTICO ERP · Nova atualização"' in worker
