/// <reference types="vite/client" />

export type Product = {
  id: string
  externalId?: string
  name: string
  sku: string
  category: string
  price: number | null
  stock: number | null
  unit: string
  specs: string[]
  art: 'cable' | 'breaker' | 'lamp' | 'tray'
  certificateUrl?: string
  analogId?: string
}

type CatalogProduct = {
  id?: string
  external_id: string | null
  article: string
  name: string
  category: string | null
  characteristics: Record<string, unknown>
  cached_price: string | number | null
  cached_stock_by_location: Record<string, number> | null
  cached_available: boolean | null
  fresh?: boolean
  source_fields?: Record<string, unknown> | null
}

export type Offer = {
  offer_id: string
  article: string
  quantity: number
  price_at_offer: string
  expires_at: string
}

type ChatReply = {
  assistant_message: { content: string }
  analysis: { intent: string; article: string | null; quantity: number | null }
  candidates: CatalogProduct[]
  current_data: { article: string } | null
  attachment_items: { candidates: CatalogProduct[] }[]
}

// Same-origin proxy by default. "demo" explicitly enables the old offline demo.
export const apiBase = (import.meta.env?.VITE_ASSISTANT_API_BASE as string | undefined)?.replace(/\/$/, '') || '/api'
export const apiEnabled = apiBase !== 'demo'
const sessionKey = `ekt-chat-session:${apiBase}`
let sessionPromise: Promise<string> | undefined

const errors: Record<string, string> = {
  offer_precondition_failed: 'Сервер не смог проверить товар и остаток для предложения. В этой версии подключение корзины EKT недоступно. Товар не добавлен.',
  offer_conflict: 'Предложение больше нельзя подтвердить. Запросите новое.',
  catalog_unavailable: 'Источник каталога недоступен. Демонстрационные данные вместо него не подставляются.',
  catalog_authentication_failed: 'Сервер не смог авторизоваться в каталоге EKT.',
  catalog_data_invalid: 'Сервер не смог разобрать данные каталога.',
  validation_error: 'Проверьте сообщение, количество или формат файла.',
  unsupported_attachment: 'Поддерживаются PDF, DOCX, XLSX, JPEG и PNG.',
  attachment_too_large: 'Выберите файл размером до 10 МБ.',
  attachment_processing_failed: 'Не удалось прочитать файл. Проверьте его содержимое.',
  not_found: 'Товар, вложение или сессия не найдены. Обновите страницу и повторите запрос.',
  internal_error: 'Ошибка сервера. Проверьте доступность PostgreSQL и миграции.',
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...options,
      signal: options.signal ?? AbortSignal.timeout(30000),
      headers: { ...(typeof options.body === 'string' ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    })
  } catch {
    throw new Error('Нет связи с FastAPI. Проверьте, что бэкенд запущен, и повторите запрос.')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errors[body?.code] || `Сервер отклонил запрос (HTTP ${response.status}).`)
  if (!body) throw new Error('Сервер вернул неожиданный ответ. Проверьте адрес API.')
  return body as T
}

export async function getSession(): Promise<string> {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      let stored: string | null = null
      try { stored = sessionStorage.getItem(sessionKey) } catch { /* Storage can be disabled. */ }
      if (stored && /^[0-9a-f-]{36}$/i.test(stored)) return stored
      const session = await request<{ id: string }>('/chat/sessions', { method: 'POST' })
      try { sessionStorage.setItem(sessionKey, session.id) } catch { /* Keep the session in memory. */ }
      return session.id
    })().catch(error => { sessionPromise = undefined; throw error })
  }
  return sessionPromise
}

export async function history() {
  const id = await getSession()
  return request<{ messages: { role: 'user' | 'assistant'; content: string }[] }>(`/chat/sessions/${id}/messages`)
}

export function toProduct(row: CatalogProduct): Product {
  const category = row.category === 'Кабель и провод' ? 'Кабель / Провод' : row.category || 'Прочее оборудование'
  const label = `${row.name} ${category}`.toLowerCase()
  const art = /кабел|провод/.test(label) ? 'cable' : /автомат|выключатель/.test(label) ? 'breaker' : /ламп|светиль/.test(label) ? 'lamp' : 'tray'
  const amount = row.fresh && row.cached_price != null ? Number(row.cached_price) : null
  const stocks = row.fresh ? row.cached_stock_by_location : null
  const stock = stocks && Object.values(stocks).every(value => Number.isFinite(value) && value >= 0)
    ? Object.values(stocks).reduce((sum, value) => sum + value, 0) : null
  return {
    id: row.article, externalId: row.external_id || undefined, sku: row.article,
    name: row.name, category, art,
    price: amount !== null && Number.isFinite(amount) && amount >= 0 ? amount : null,
    stock: row.cached_available === false && row.fresh ? 0 : stock,
    unit: typeof row.source_fields?.unit === 'string' ? row.source_fields.unit : '',
    specs: Object.entries(row.characteristics).map(([key, value]) => `${key}: ${String(value)}`),
  }
}

export async function freshProduct(article: string, signal?: AbortSignal) {
  return toProduct(await request<CatalogProduct>(`/catalog/products/${encodeURIComponent(article)}/fresh`, { signal }))
}

async function refreshCards(rows: CatalogProduct[], signal?: AbortSignal) {
  return Promise.all(rows.map(async row => {
    try { return await freshProduct(row.article, signal) }
    catch { return toProduct(row) } // Indexed details remain visible; stale price/stock never do.
  }))
}

export async function searchCatalog(query: string, signal?: AbortSignal) {
  const data = await request<{ candidates: CatalogProduct[] }>(`/catalog/search?${new URLSearchParams({ q: query, limit: '100' })}`, { signal })
  return refreshCards(data.candidates, signal)
}

export async function sendMessage(content: string, attachmentIds: string[] = []) {
  const id = await getSession()
  const data = await request<ChatReply>(`/chat/sessions/${id}/messages`, {
    method: 'POST', body: JSON.stringify({ content, attachment_ids: attachmentIds }),
  })
  const rows = [...data.candidates, ...data.attachment_items.flatMap(item => item.candidates)]
  const unique = [...new Map(rows.map(row => [row.article, row])).values()]
  const cards = await refreshCards(unique)
  if (data.current_data?.article && !cards.some(card => card.sku === data.current_data?.article)) {
    try { cards.push(await freshProduct(data.current_data.article)) } catch { /* Keep the server's availability explanation. */ }
  }
  return { text: data.assistant_message.content, cards, analysis: data.analysis }
}

export async function uploadAttachment(file: File) {
  const id = await getSession()
  const body = new FormData()
  body.append('file', file)
  return request<{ id: string; warnings: string[] }>(`/chat/sessions/${id}/attachments`, { method: 'POST', body })
}

export async function createOffer(product: Product, quantity: number) {
  if (!product.externalId) throw new Error('В каталоге нет идентификатора товара для корзины.')
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 10000) throw new Error('Количество должно быть целым числом от 1 до 10000.')
  const id = await getSession()
  return request<Offer>(`/chat/sessions/${id}/offers`, {
    method: 'POST', body: JSON.stringify({ product_identifier: product.externalId, article: product.sku, quantity }),
  })
}

export async function confirmOffer(offerId: string, idempotencyKey: string) {
  const id = await getSession()
  return request<{ offer: Offer; outcome: string; message: string; cart_url: string | null }>(`/chat/sessions/${id}/offers/${encodeURIComponent(offerId)}/confirm`, {
    method: 'POST', headers: { 'Idempotency-Key': idempotencyKey },
  })
}
