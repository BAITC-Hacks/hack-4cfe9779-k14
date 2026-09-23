/// <reference types="vite/client" />

export type Product = {
  id: string
  externalId?: string
  imageUrl?: string
  sourceUrl?: string
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
  analogs?: { product: CatalogProduct }[]
  pending_offer?: Offer | null
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
  internal_error: 'Ошибка сервера. Повторите запрос позже.',
}

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...options,
      signal: options.signal ?? AbortSignal.timeout(60000),
      headers: { ...(typeof options.body === 'string' ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    })
  } catch {
    throw new Error('Нет связи с сервером. Повторите запрос позже.')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(errors[body?.code] || `Сервер отклонил запрос (HTTP ${response.status}).`, response.status)
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
  type History = { messages: { role: 'user' | 'assistant'; content: string }[] }
  let id = await getSession()
  try { return await request<History>(`/chat/sessions/${id}/messages`) }
  catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) throw error
    // The development database may have been recreated since the last visit.
    try { sessionStorage.removeItem(sessionKey) } catch { /* Storage can be disabled. */ }
    sessionPromise = undefined
    id = await getSession()
    return request<History>(`/chat/sessions/${id}/messages`)
  }
}

export function safeSourceUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && (url.hostname === 'ekt.kz' || url.hostname.endsWith('.ekt.kz')) && !url.username && !url.password ? url.href : undefined
  } catch { return undefined }
}

export function runtimeStatus() {
  return request<{catalog_source: string; model_configured: boolean; model: string | null; cart_mode: string}>('/catalog/status')
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
    imageUrl: safeSourceUrl(row.source_fields?.image), sourceUrl: safeSourceUrl(row.source_fields?.url),
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
  const cards: Product[] = []
  // Four parallel reads bound load on the partner API while loading a page.
  for (let index = 0; index < rows.length; index += 4) {
    if (signal?.aborted) throw new Error('Загрузка отменена')
    cards.push(...await Promise.all(rows.slice(index, index + 4).map(async row => {
      try { return await freshProduct(row.article, signal) }
      catch { return toProduct(row) }
    })))
  }
  return cards
}

export async function searchCatalog(query: string, signal?: AbortSignal) {
  const path = query.trim() ? `/catalog/search?${new URLSearchParams({ q: query, limit: '100' })}` : '/catalog/products?limit=100'
  const data = await request<{ candidates: CatalogProduct[] }>(path, { signal })
  return refreshCards(data.candidates, signal)
}

export async function loadCatalogPage(page: number, signal?: AbortSignal) {
  const result = await request<{candidates: CatalogProduct[]; has_more: boolean}>(`/catalog/source-page?page=${page}`, {signal})
  return {products: await refreshCards(result.candidates, signal), hasMore: result.has_more}
}

export async function sendMessage(content: string, attachmentIds: string[] = []) {
  const id = await getSession()
  const data = await request<ChatReply>(`/chat/sessions/${id}/messages`, {
    method: 'POST', body: JSON.stringify({ content, attachment_ids: attachmentIds }),
  })
  const rows = [...data.candidates, ...data.attachment_items.flatMap(item => item.candidates), ...(data.analogs || []).map(item => item.product)]
  const unique = [...new Map(rows.map(row => [row.article, row])).values()]
  const cards = await refreshCards(unique)
  if (data.current_data?.article && !cards.some(card => card.sku === data.current_data?.article)) {
    try { cards.push(await freshProduct(data.current_data.article)) } catch { /* Keep the server's availability explanation. */ }
  }
  if (data.pending_offer && !cards.some(card => card.sku === data.pending_offer?.article)) {
    try { cards.push(await freshProduct(data.pending_offer.article)) } catch { /* Offer still has article and price. */ }
  }
  return { text: data.assistant_message.content, cards, analysis: data.analysis, offer: data.pending_offer }
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
