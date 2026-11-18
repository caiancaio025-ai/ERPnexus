"""Regras de privacidade e histórico interno V18, sem depender do PostgreSQL em produção."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.notifications.models import Notification
from app.notifications.service import activity_visible, notify_activity


@pytest.mark.parametrize(
    "role,modules,module,expected",
    [
        ("gestao", [], "financeiro", True),
        ("gestao", [], "laboratorio", True),
        ("gestao", [], "compras", True),
        ("super_admin", [], "financeiro", True),
        ("admin", ["financeiro", "laboratorio", "comercial"], "financeiro", False),
        ("admin", ["laboratorio", "comercial"], "compras", False),
        ("admin", ["laboratorio", "comercial"], "orcamentos", True),
        ("tecnico", ["dashboard", "laboratorio", "compras"], "financeiro", False),
        ("tecnico", ["dashboard", "laboratorio", "compras"], "laboratorio", True),
        ("tecnico", ["dashboard", "laboratorio"], "compras", False),
        ("lab", ["dashboard", "laboratorio"], "orcamentos", False),
        ("consulta", ["dashboard"], "estoque", False),
        ("gestao", [], "configuracoes", True),
        ("admin", ["configuracoes"], "configuracoes", False),
        ("tecnico", ["configuracoes"], "configuracoes", False),
    ],
)
def test_role_scope_is_enforced(role, modules, module, expected):
    assert activity_visible(role, modules, module) is expected


@pytest.mark.asyncio
async def test_actor_included_and_finance_excluded_from_admin_technicians():
    users = [
        SimpleNamespace(id=1, role="gestao", modules=[], name="Gestão", is_active=True),
        SimpleNamespace(id=2, role="admin", modules=["comercial", "financeiro"], name="ADM", is_active=True),
        SimpleNamespace(id=3, role="tecnico", modules=["laboratorio", "compras"], name="Técnico", is_active=True),
    ]

    class FakeResult:
        def all(self):
            return users

    class Db:
        def __init__(self):
            self.added = []

        async def scalars(self, stmt):
            return FakeResult()

        def add(self, item):
            self.added.append(item)

    db = Db()
    await notify_activity(db, actor=users[2], activity_module="financeiro", action="finance_entry_created",
                          title="Lançamento financeiro", message="Operação financeira registrada.")
    assert [item.user_id for item in db.added] == [1]
    db.added.clear()
    await notify_activity(db, actor=users[2], activity_module="laboratorio", action="analysis_completed",
                          title="OS 39405 - Analisada", message="Análise concluída.", work_order_id=123,
                          work_order_number="39405", equipment_name="Inversor WEG CFW11")
    assert {item.user_id for item in db.added} == {1, 3}
    assert all(item.actor_name == "Técnico" for item in db.added)
    assert all(item.work_order_number == "39405" for item in db.added)
    assert all(item.amount is None for item in db.added)
    assert all(item.push_processed_at is not None for item in db.added)
    assert all(isinstance(item, Notification) for item in db.added)
    db.added.clear()
    await notify_activity(db, actor=users[2], activity_module="orcamentos", action="quote_created",
                          title="Orçamento", message="Revisão criada")
    assert {item.user_id for item in db.added} == {1, 2}


def test_migration_and_scope_endpoint_are_additive():
    root = Path(__file__).parents[1]
    migration = (root / "migrations/versions/20261117_01_notification_activity_history.py").read_text()
    router = (root / "app/notifications/router.py").read_text()
    assert 'down_revision = "20261116_01"' in migration
    assert 'op.add_column("notifications", column)' in migration
    assert 'Notification.user_id == user.id, _visible_predicate(user)' in router
    assert 'if module and not activity_visible(user.role, user.modules, module)' in router
    assert '@router.get("/history", response_model=NotificationHistory)' in router
    assert '@router.get("/actors")' in router


def test_no_external_push_delivery_or_browser_prompts():
    root = Path(__file__).parents[1]
    main = (root / "app/main.py").read_text()
    dashboard = (root.parent / "web/src/features/dashboard/Dashboard.tsx").read_text()
    assert "push_delivery_loop" not in main
    assert "PushNotificationsToggle" not in dashboard
    assert 'navigate("/notificacoes")' in dashboard
