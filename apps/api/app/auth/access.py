from collections.abc import Iterable

MODULE_DASHBOARD = "dashboard"
MODULE_FINANCE = "financeiro"
MODULE_PURCHASING = "compras"
MODULE_COMMERCIAL = "comercial"
MODULE_LABORATORY = "laboratorio"
MODULE_INVENTORY = "estoque"
MODULE_SETTINGS = "configuracoes"
MODULE_AUDIT = "auditoria"
MODULE_EMPLOYEES = "colaboradores"

AVAILABLE_MODULES = (
    MODULE_DASHBOARD,
    MODULE_FINANCE,
    MODULE_PURCHASING,
    MODULE_COMMERCIAL,
    MODULE_LABORATORY,
    MODULE_INVENTORY,
    MODULE_SETTINGS,
    MODULE_AUDIT,
    MODULE_EMPLOYEES,
)

AVAILABLE_ROLES = (
    "super_admin",
    "admin",
    "financeiro",
    "compras",
    "comercial",
    "laboratorio",
    "estoque",
    "consulta",
    "rh",
)

ADMIN_ROLES = {"super_admin", "admin"}

ROLE_DEFAULT_MODULES: dict[str, tuple[str, ...]] = {
    "super_admin": AVAILABLE_MODULES,
    "admin": AVAILABLE_MODULES,
    "financeiro": (MODULE_DASHBOARD, MODULE_FINANCE),
    "compras": (MODULE_DASHBOARD, MODULE_PURCHASING),
    "comercial": (MODULE_DASHBOARD, MODULE_COMMERCIAL),
    "laboratorio": (MODULE_DASHBOARD, MODULE_LABORATORY),
    "estoque": (MODULE_DASHBOARD, MODULE_INVENTORY),
    "consulta": (MODULE_DASHBOARD,),
    "rh": (MODULE_DASHBOARD, MODULE_EMPLOYEES),
}


def normalize_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in AVAILABLE_ROLES:
        raise ValueError("Perfil de usuário inválido.")
    return normalized


def normalize_modules(role: str, modules: Iterable[str] | None) -> list[str]:
    normalized_role = normalize_role(role)
    if normalized_role in ADMIN_ROLES:
        return list(AVAILABLE_MODULES)

    selected = {MODULE_DASHBOARD}
    if modules is None:
        selected.update(ROLE_DEFAULT_MODULES[normalized_role])
    else:
        for module in modules:
            normalized = module.strip().lower()
            if normalized not in AVAILABLE_MODULES:
                raise ValueError(f"Módulo inválido: {module}.")
            if normalized not in {MODULE_SETTINGS, MODULE_AUDIT}:
                selected.add(normalized)

    return [module for module in AVAILABLE_MODULES if module in selected]


def user_has_module(role: str, modules: Iterable[str] | None, module: str) -> bool:
    if role in ADMIN_ROLES:
        return True
    return module in set(modules or ())
