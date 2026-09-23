# EKT API adapter

`EktClient` performs authenticated read-only requests. `LiveEktResponseMapper` maps the list/detail responses observed on 2026-09-23; `EktCatalogAdapter` exposes normalized application-owned products.

## Observed contract

- `GET /api/products?page=N`: `{page, per_page, count, items}`. Observed page size: 20. Items contain `id`, `article`, `name`, `price`, `image`, `url`, `url_api_detail`, `offers`.
- `GET /api/products/detail?id=ID`: product fields plus `description`, `quantity`, `stores: [{id, name, quantity}]`, `properties`.
- Basic Auth stays on the server. No confirmed cart, checkout or customer-session endpoints were supplied.

The mapper preserves SKU strings (including underscores, Cyrillic and leading zeros), price, stores, properties and source URLs. Images/links are restricted to HTTPS EKT hosts. Category comes from a recognized source URL segment, otherwise remains unknown. Certificates and units are not invented. Fractional stock currently remains unknown because the backend quantity contract is integer-only. Contradictions between name/description/properties remain visible, rather than being silently reconciled.

`source_field_presence` distinguishes missing fields from explicit null/zero/empty values. The local index is search data only: UI prices and stock are displayed after a successful detail refresh; failed refreshes do not reuse cached numbers as current data.

## Paging and search

Startup loads `CATALOG_SYNC_PAGES` pages (default 5). The UI loads additional pages with `GET /api/catalog/source-page?page=N`. A non-empty page is treated as having a possible next page; one final empty request can occur. This is a partial index, not a claim that the entire EKT catalog was imported.

Detail refresh uses an indexed article's `external_id`, avoiding a repeated catalog crawl. Unknown articles outside the loaded index return no match. No undocumented partner search parameter is invented. To import a known detail: `python -m app.catalog_sync --product-id 515291` (host execution requires `PYTHONPATH=src`). To expand the initial index, increase `CATALOG_SYNC_PAGES` and run sync. Search by properties requires detail records, since list rows omit them.

## Configuration and security

Set `EKT_API_USERNAME`, `EKT_API_PASSWORD` in the ignored server `.env`. Base URL defaults to `https://ekt.kz/api/`. Without EKT credentials the catalog stays unavailable. Backend runtime mock integrations were removed in dev2; the cart gateway remains unavailable.

Credentials never go into browser code, Git, model inputs or HTTP logs. Redirects are disabled to avoid forwarding Basic Auth. GET retries apply only to connection/timeouts/5xx (`EKT_READ_RETRY_COUNT`, default 1, max 3; `EKT_RETRY_BACKOFF_SECONDS`, default 0.05). Auth, malformed JSON and other 4xx responses are not retried. Partner rate limits, price/tax terms and cart contracts still need confirmation.
