WORK_ORDER_STATUSES = (
    "received", "awaiting_analysis", "in_analysis", "awaiting_quote",
    "quote_sent", "awaiting_approval", "approved", "rejected",
    "awaiting_parts", "in_repair", "in_testing", "completed",
    "awaiting_pickup", "delivered", "warranty", "invoiced",
    "cancelled", "no_repair",
)

BUSINESS_STATUS_TARGETS = {
    "received", "awaiting_approval", "in_analysis", "approved",
    "no_repair", "awaiting_pickup", "warranty", "invoiced",
}

LEGACY_SUBSTATUS_TARGETS = {
    "quote_sent": "quote_sent",
    "completed": "awaiting_delivery",
    "delivered": "delivered",
}

SELECTABLE_BUILTIN_STATUSES = set(WORK_ORDER_STATUSES)

def can_transition(current: str, target: str) -> bool:
    """Allow free movement between valid main statuses.

    The laboratory operation intentionally does not enforce a hierarchy of
    statuses. History/audit remains the source of traceability.
    """
    if current not in WORK_ORDER_STATUSES or target not in WORK_ORDER_STATUSES:
        return False
    return True
