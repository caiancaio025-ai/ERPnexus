WORK_ORDER_STATUSES = (
    "received",
    "awaiting_analysis",
    "in_analysis",
    "awaiting_quote",
    "quote_sent",
    "awaiting_approval",
    "approved",
    "rejected",
    "awaiting_parts",
    "in_repair",
    "in_testing",
    "completed",
    "awaiting_pickup",
    "delivered",
    "warranty",
    "invoiced",
    "cancelled",
    "no_repair",
)

BUSINESS_STATUS_TARGETS = {
    "received",  # Entrada
    "awaiting_approval",  # Ag. Aprovação
    "in_analysis",  # Em análise
    "approved",  # Aprovado
    "no_repair",  # Sem conserto
    "awaiting_pickup",  # Liberado
    "warranty",  # Garantia
    "invoiced",  # Faturado
}

# Esses códigos continuam reconhecidos para leitura de dados históricos e para
# permitir que uma OS antiga avance no fluxo. Novas alterações não devem mais
# gravá-los como status principal; eles foram substituídos por substatus.
LEGACY_SUBSTATUS_TARGETS = {
    "quote_sent": "quote_sent",
    "completed": "awaiting_delivery",
    "delivered": "delivered",
}

# A partir deste checkpoint, usuarios com acesso ao modulo Laboratorio podem
# selecionar livremente qualquer status principal valido. Os codigos abaixo
# continuam reservados como substatus e nao podem voltar a ser gravados como
# status principal.
SELECTABLE_BUILTIN_STATUSES = set(WORK_ORDER_STATUSES) - set(LEGACY_SUBSTATUS_TARGETS)


def can_transition(current: str, target: str) -> bool:
    """Valida apenas a existencia do status; nao ha mais hierarquia operacional.

    Status legados convertidos em substatus permanecem bloqueados como destino
    principal para evitar duas fontes de verdade (status + substatus).
    """
    if current not in WORK_ORDER_STATUSES or target not in WORK_ORDER_STATUSES:
        return False
    if target in LEGACY_SUBSTATUS_TARGETS:
        return False
    return True
