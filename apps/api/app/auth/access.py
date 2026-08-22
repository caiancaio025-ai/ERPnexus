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

# Perfis oficiais nesta fase: ADM, GESTAO e LAB.
# Perfis legados permanecem aceitos para não quebrar usuários já existentes.
AVAILABLE_ROLES = (
    "super_admin",
    "admin",
    "gestao",
    "lab",
    "tecnico",
    "financeiro",
    "compras",
    "comercial",
    "laboratorio",
    "estoque",
    "consulta",
    "rh",
)

# ADM e GESTAO possuem acesso funcional geral. super_admin é legado/bootstrap.
ADMIN_ROLES = {"super_admin", "admin", "gestao"}
# Somente GESTAO administra colaboradores. super_admin é aceito apenas como
# compatibilidade do usuário bootstrap já existente e equivale a GESTAO.
COLLABORATOR_MANAGER_ROLES = {"super_admin", "gestao"}

LAB_MODULES = (
    MODULE_DASHBOARD,
    MODULE_PURCHASING,
    MODULE_COMMERCIAL,
    MODULE_LABORATORY,
    MODULE_INVENTORY,
    MODULE_EMPLOYEES,
)

ROLE_DEFAULT_MODULES: dict[str, tuple[str, ...]] = {
    "super_admin": AVAILABLE_MODULES,
    "admin": AVAILABLE_MODULES,
    "gestao": AVAILABLE_MODULES,
    "lab": LAB_MODULES,
    # Alias legado: técnico passa a ter a mesma matriz do perfil LAB.
    "tecnico": LAB_MODULES,
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
    if not modules:
        selected.update(ROLE_DEFAULT_MODULES[normalized_role])
    else:
        for module in modules:
            normalized = module.strip().lower()
            if normalized not in AVAILABLE_MODULES:
                raise ValueError(f"Módulo inválido: {module}.")
            if normalized not in {MODULE_SETTINGS, MODULE_AUDIT, MODULE_FINANCE}:
                selected.add(normalized)

    return [module for module in AVAILABLE_MODULES if module in selected]


def user_has_module(role: str, modules: Iterable[str] | None, module: str) -> bool:
    normalized = role.strip().lower()
    if normalized in ADMIN_ROLES:
        return True
    return module in set(modules or ())


def user_can_manage_collaborators(role: str) -> bool:
    return role.strip().lower() in COLLABORATOR_MANAGER_ROLES


def user_can_create_quote(role: str, modules: Iterable[str] | None) -> bool:
    """Retorna se o usuário pode criar, editar ou emitir orçamento comercial."""
    normalized = role.strip().lower()
    if normalized in {"super_admin", "admin", "gestao", "management", "comercial"}:
        return True
    if normalized in {"lab", "tecnico", "technician"}:
        return False
    return False
