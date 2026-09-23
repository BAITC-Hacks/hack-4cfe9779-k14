"""The reviewable source of purchase-condition placeholders for local demo."""

from app.schemas.purchase_conditions import PurchaseConditions


DEMO_PURCHASE_CONDITIONS = PurchaseConditions(
    source_label="demo placeholder configuration",
    is_demo=True,
    payment_methods=None,
    delivery=None,
    minimum_order=None,
    notice=(
        "DEMO: утверждённые условия покупки ekt.kz не предоставлены. "
        "Способы оплаты, доставка и минимальная партия требуют подтверждения партнёра."
    ),
)
