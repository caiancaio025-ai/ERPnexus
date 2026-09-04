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
    "in_analysis",  # Analisado
    "approved",  # Aprovado
    "no_repair",  # Sem conserto
    "completed",  # Pronto
    "awaiting_pickup",  # Liberado
    "warranty",  # Garantia
    "invoiced",  # Faturado
}

# O NEXUS possui dois níveis de leitura do processo:
# 1) marcos comerciais históricos (Entrada, Ag. Aprovação, Analisado, ...)
# 2) etapas operacionais detalhadas (ag. peças, reparo, testes, ...)
#
# A matriz abaixo preserva governança sem obrigar o laboratório a percorrer
# dezenas de cliques. O operador pode avançar para um marco comercial e, ao
# mesmo tempo, Compras/Materiais continuam usando as etapas técnicas.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "received": {"awaiting_analysis", "in_analysis", "awaiting_approval", "no_repair", "cancelled"},
    "awaiting_analysis": {"in_analysis", "awaiting_approval", "no_repair", "cancelled"},
    "in_analysis": {
        "awaiting_quote",
        "quote_sent",
        "awaiting_approval",
        "approved",
        "in_repair",
        "no_repair",
        "cancelled",
    },
    "awaiting_quote": {"quote_sent", "awaiting_approval", "approved", "no_repair", "cancelled"},
    "quote_sent": {"awaiting_approval", "approved", "rejected", "no_repair", "cancelled"},
    "awaiting_approval": {"approved", "rejected", "no_repair", "cancelled"},
    "approved": {
        "awaiting_parts",
        "in_repair",
        "in_testing",
        "completed",
        "no_repair",
        "cancelled",
    },
    "rejected": {"awaiting_approval", "approved", "no_repair", "cancelled"},
    "awaiting_parts": {
        "approved",
        "in_repair",
        "in_testing",
        "completed",
        "no_repair",
        "cancelled",
    },
    "in_repair": {
        "approved",
        "awaiting_parts",
        "in_testing",
        "completed",
        "no_repair",
        "cancelled",
    },
    "in_testing": {"in_repair", "awaiting_parts", "completed", "no_repair", "cancelled"},
    "completed": {"awaiting_pickup", "delivered", "invoiced", "warranty", "in_repair"},
    "awaiting_pickup": {"delivered", "invoiced", "warranty", "in_repair"},
    "delivered": {"invoiced", "warranty"},
    "warranty": {
        "in_analysis",
        "approved",
        "awaiting_parts",
        "in_repair",
        "in_testing",
        "completed",
        "no_repair",
    },
    "invoiced": {"warranty"},
    "cancelled": {"received"},
    "no_repair": {"awaiting_pickup", "delivered", "invoiced", "warranty", "in_analysis"},
}


def can_transition(current: str, target: str) -> bool:
    if current not in WORK_ORDER_STATUSES or target not in WORK_ORDER_STATUSES:
        return False
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, set())
