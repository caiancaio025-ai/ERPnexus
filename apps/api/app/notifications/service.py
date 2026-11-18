from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_create_quote, user_has_module
from app.auth.models import User
from app.notifications.models import Notification


async def notify_modules(
    db: AsyncSession,
    *,
    modules: set[str],
    category: str,
    title: str,
    message: str,
    target: str | None = None,
    severity: str = "info",
    entity_type: str | None = None,
    entity_id: int | None = None,
    work_order_id: int | None = None,
    amount: Decimal | None = None,
    exclude_user_id: int | None = None,
) -> None:
    users = list((await db.scalars(select(User).where(User.is_active.is_(True)))).all())
    for user in users:
        if exclude_user_id is not None and user.id == exclude_user_id:
            continue
        scope = "financeiro" if "financeiro" in modules else (
            "orcamentos" if category in {"quote", "commercial_sale_approved"} else
            ("compras" if "compras" in modules else next(iter(modules), None))
        )
        if activity_visible(user.role, user.modules, scope):
            db.add(
                Notification(
                    user_id=user.id,
                    category=category,
                    activity_module=scope,
                    push_processed_at=datetime.now(UTC),
                    severity=severity,
                    title=title,
                    message=message,
                    target=target,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    work_order_id=work_order_id,
                    amount=amount,
                )
            )


async def notify_roles(
    db: AsyncSession,
    *,
    roles: set[str],
    category: str,
    title: str,
    message: str,
    target: str | None = None,
    severity: str = "info",
    entity_type: str | None = None,
    entity_id: int | None = None,
    work_order_id: int | None = None,
    amount: Decimal | None = None,
    exclude_user_id: int | None = None,
) -> None:
    """Notify active users by explicit role, without widening module permissions."""
    normalized_roles = {role.strip().lower() for role in roles}
    users = list((await db.scalars(select(User).where(User.is_active.is_(True)))).all())
    for user in users:
        if exclude_user_id is not None and user.id == exclude_user_id:
            continue
        if user.role.strip().lower() not in normalized_roles or not activity_visible(user.role, user.modules, "orcamentos" if category == "quote" else None):
            continue
        db.add(
            Notification(
                user_id=user.id,
                category=category,
                activity_module="orcamentos" if category == "quote" else None,
                push_processed_at=datetime.now(UTC),
                severity=severity,
                title=title,
                message=message,
                target=target,
                entity_type=entity_type,
                entity_id=entity_id,
                work_order_id=work_order_id,
                amount=amount,
            )
        )


async def notify_quote_users(
    db: AsyncSession,
    *,
    category: str,
    title: str,
    message: str,
    target: str | None = None,
    severity: str = "info",
    entity_type: str | None = None,
    entity_id: int | None = None,
    work_order_id: int | None = None,
    exclude_user_id: int | None = None,
) -> None:
    """Notify only active users authorized to create/emit quotes."""
    users = list((await db.scalars(select(User).where(User.is_active.is_(True)))).all())
    for user in users:
        if exclude_user_id is not None and user.id == exclude_user_id:
            continue
        if user_can_create_quote(user.role, user.modules):
            db.add(Notification(
                user_id=user.id,
                category=category,
                activity_module="orcamentos",
                push_processed_at=datetime.now(UTC),
                severity=severity,
                title=title,
                message=message,
                target=target,
                entity_type=entity_type,
                entity_id=entity_id,
                work_order_id=work_order_id,
            ))


# Permissões de visualização: ADM recebe apenas orçamentos; LAB nunca vê financeiro.
MODULES = {"laboratorio", "orcamentos", "compras", "estoque", "comercial", "financeiro", "colaboradores", "configuracoes"}


def activity_visible(role: str, modules: list[str] | None, activity_module: str | None) -> bool:
    role = role.strip().lower()
    if role in {"super_admin", "gestao"}:
        return True
    if not activity_module or activity_module not in MODULES:
        return False
    if role == "admin":
        return activity_module == "orcamentos"
    if activity_module in {"financeiro", "configuracoes"}:
        return False
    if activity_module == "orcamentos":
        return user_can_create_quote(role, modules)
    if activity_module == "laboratorio":
        return user_has_module(role, modules, "laboratorio")
    if activity_module == "colaboradores":
        return user_has_module(role, modules, "colaboradores")
    return user_has_module(role, modules, activity_module)


# Itens legados da V16/V17 não têm coluna de módulo; classificar com lista fechada.
LEGACY_CATEGORY_MODULE = {
    "quote": "orcamentos", "commercial_sale_approved": "orcamentos",
    "purchase": "compras", "purchase_request": "compras",
    "material_request_approved": "compras", "finance": "financeiro",
    "financeiro": "financeiro", "billing": "financeiro",
}


def visible_notification_module(item: Notification) -> str | None:
    return item.activity_module or LEGACY_CATEGORY_MODULE.get(item.category)


async def notify_activity(
    db: AsyncSession, *, actor: User, activity_module: str, action: str,
    title: str, message: str, target: str | None = None,
    severity: str = "info", entity_type: str | None = None,
    entity_id: int | None = None, work_order_id: int | None = None,
    work_order_number: str | int | None = None,
    equipment_name: str | None = None, details: str | None = None,
    exclude_roles: set[str] | None = None,
) -> None:
    """Salva o fato na mesma transação da alteração, para todos os perfis autorizados.

    Inclui o ator quando autorizado. Nunca colocar valores financeiros em eventos
    compartilhados; até o texto é preparado pelo evento no domínio.
    """
    if activity_module not in MODULES:
        raise ValueError("Módulo de atividade não permitido.")
    users = list((await db.scalars(select(User).where(User.is_active.is_(True)))).all())
    for recipient in users:
        if exclude_roles and recipient.role.strip().lower() in exclude_roles:
            continue
        if not activity_visible(recipient.role, recipient.modules, activity_module):
            continue
        db.add(Notification(
            user_id=recipient.id, category=activity_module, activity_module=activity_module,
            action=action, actor_user_id=actor.id, actor_name=actor.name,
            severity=severity, title=title, message=message,
            target=target, entity_type=entity_type, entity_id=entity_id,
            work_order_id=work_order_id,
            work_order_number=str(work_order_number) if work_order_number is not None else None,
            equipment_name=equipment_name, details=details,
            # Mensagem exclusivamente interna; não colocá-la na fila Web Push.
            push_processed_at=datetime.now(UTC),
        ))
