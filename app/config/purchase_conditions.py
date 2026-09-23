"""Safe default while approved purchase conditions are unavailable."""

from app.schemas.purchase_conditions import PurchaseConditions


UNAVAILABLE_PURCHASE_CONDITIONS = PurchaseConditions(
    source_label="unavailable/no approved purchase conditions",
    payment_methods=None,
    delivery=None,
    minimum_order=None,
    notice=(
        "Утверждённые условия покупки ekt.kz не предоставлены. "
        "Способы оплаты, доставка и минимальная партия требуют подтверждения партнёра."
    ),
)
