# EKT API adapter

`app/integrations/ekt_client.py` is the HTTP boundary between this service and ekt.kz. `EktCatalogAdapter` translates its normalized `EktProduct` into the application-owned catalog model; services never receive the partner JSON envelope or field names.

## Confirmed contract and unknowns

Project-provided materials from the earlier MVP brief confirm Basic Auth and these read endpoints/parameters:

- `GET /api/products?page=<number>` — product catalog page.
- `GET /api/products/detail?id=<partner-id>` — product details.

The exact response envelopes, field names/types, pagination termination metadata, currency/price semantics, stock representation, rate limits, and cart endpoints are not present in the repository. They must be obtained from the ekt.kz partner documentation. No cart read/write methods are implemented because no cart endpoint is confirmed.

The adapter deliberately requires an `EktResponseMapper` in its constructor. Implement `parse_products_page(payload)` and `parse_product_detail(payload)` only after obtaining the actual JSON schema. The mapper converts partner JSON into the strict internal Pydantic `EktProduct`; no external-format dictionaries should be passed into route or service code. The test mapper is illustrative mock data, not an assertion about ekt.kz.

For each optional mapped field, the real mapper must set `source_field_presence`: `false` means the partner omitted the field, while `true` together with `null`, `0` or `[]` preserves the source's actual supplied value. Do not fill missing category, certificates, price, stock or availability values with defaults.

## Client methods

- `get_products_page(page=1)` calls the confirmed catalog path and normalizes the response.
- `get_product_by_article(article, max_pages=100)` scans catalog pages using the confirmed `page` parameter and exact article equality. Since a server-side article search parameter and page-count envelope are undocumented, this bounded fallback can be inefficient. Confirm a proper search operation and pagination metadata with EKT.
- `get_product_details(product_id)` calls the confirmed detail path.
- `check_price(article)` looks up the article, refreshes its detail, and returns price only when the mapper supplied one.
- `check_stock(article)` refreshes details and returns normalized stock by location only when supplied.

Retries are controlled with `EKT_READ_RETRY_COUNT` (default `1`, maximum `3`) and `EKT_RETRY_BACKOFF_SECONDS` (default `0.05`). They apply only to safe GET requests and only after timeout, connection or 5xx errors. Authentication, malformed response and 4xx errors are not retried. Never automatically retry cart writes unless the partner documents an idempotency guarantee.

## Configuration and security

Set these server environment variables (or corresponding entries in the ignored `.env`):

- `EKT_API_BASE_URL` — default `https://ekt.kz/api/`.
- `EKT_API_USERNAME` — partner Basic Auth username.
- `EKT_API_PASSWORD` — partner Basic Auth password.
- `EKT_READ_RETRY_COUNT` and `EKT_RETRY_BACKOFF_SECONDS` — bounded GET retry policy.
- `CATALOG_ADAPTER_MODE` — `mock` by default; `ekt` remains unavailable until the partner mapper is implemented.

Credentials are read by Pydantic Settings and passed to `httpx.BasicAuth` server-side. They are not returned to clients. Error logs include an event type, operation, HTTP status, and exception class only; they omit URLs, headers, bodies, and credentials. Redirects are disabled so Basic Auth is not forwarded to a redirect target. Timeouts default to 8 seconds overall and 3 seconds for connection establishment.

Example wiring (after a real mapper is implemented):

```python
async with EktClient(ConfirmedEktResponseMapper()) as ekt:
    product = await ekt.get_product_by_article("verified-article")
    latest = await ekt.get_product_details(product.id)
```

Do not create a placeholder mapper that guesses partner field names. Until the schema is supplied, construction of the transport works but integrations should not be wired into user-facing behavior.
