# Условия покупки

Условия покупки не являются знанием LLM. `PurchaseConditionsProvider` — отдельный утверждаемый источник, который `ChatService` читает только при intent `purchase_conditions`.

По умолчанию [`app/config/purchase_conditions.py`](../app/config/purchase_conditions.py) содержит явный `DEMO` placeholder: реальные условия ekt.kz не предоставлены, поэтому оплата, доставка и минимальная партия не сообщаются как факты. Этот файл — единственная reviewable точка demo-конфигурации.

Для production нужен provider, получающий утверждённую версию условий (владелец, дата вступления в силу, способы оплаты, доставка, минимальная партия, ограничения и региональные исключения). Его следует подключить в dependency composition, не добавляя условия в system prompt.
