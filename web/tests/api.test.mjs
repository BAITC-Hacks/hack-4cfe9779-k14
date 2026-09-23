import assert from 'node:assert/strict'
import test from 'node:test'
import { toProduct, searchCatalog, sendMessage, uploadAttachment, createOffer, confirmOffer, history } from '../src/api.ts'

const row = {
  article: 'DEMO-1', external_id: 'remote-1', name: 'Кабель', category: 'Кабель и провод',
  characteristics: { cores: 3 }, cached_price: '12.50', cached_stock_by_location: { A: 3, B: 4 }, cached_available: true,
}

test('unknown and cached values never become fresh zero price/stock', () => {
  assert.equal(toProduct(row).price, null)
  assert.equal(toProduct(row).stock, null)
  assert.equal(toProduct({ ...row, fresh: true }).stock, 7)
  assert.equal(toProduct({ ...row, fresh: true }).price, 12.5)
  assert.equal(toProduct({ ...row, fresh: true, cached_price: null }).price, null)
  assert.equal(toProduct({ ...row, fresh: true, cached_stock_by_location: null }).stock, null)
  assert.equal(toProduct({ ...row, fresh: true, cached_price: 'invalid' }).price, null)
})

test('FastAPI contract: session, content, uploads, offers and idempotent confirmation', async () => {
  const calls = []
  const previousFetch = globalThis.fetch
  const previousStorage = globalThis.sessionStorage
  globalThis.sessionStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }
  let failFresh = false
  let missingSession = true
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    let body
    if (url === '/api/chat/sessions') body = { id: '6b242946-4784-4514-bb13-a9b3c1043557' }
    else if (url.endsWith('/fresh')) return Response.json(failFresh ? { code: 'catalog_unavailable' } : { ...row, fresh: true }, { status: failFresh ? 503 : 200 })
    else if (url.includes('/catalog/products?')) body = { candidates: [row] }
    else if (url.endsWith('/messages') && !options.method) {
      if (missingSession) { missingSession = false; return Response.json({code: 'not_found'}, {status: 404}) }
      body = {messages: []}
    }
    else if (url.endsWith('/messages')) body = { assistant_message: { content: 'Ответ сервера' }, candidates: [row], current_data: null, attachment_items: [], analysis: { intent: 'find_product' } }
    else if (url.endsWith('/attachments')) body = { id: 'attachment-1', warnings: [] }
    else if (url.endsWith('/offers')) body = { offer_id: 'offer-1', article: row.article, quantity: 2 }
    else if (url.endsWith('/confirm')) body = { outcome: 'cart_unavailable', message: 'Cart unavailable', cart_url: null }
    else throw new Error(`Unexpected endpoint ${url}`)
    return Response.json(body)
  }
  try {
    const cards = await searchCatalog('')
    assert.equal(cards[0].stock, 7)
    failFresh = true
    assert.equal((await searchCatalog(''))[0].price, null)
    failFresh = false
    const reply = await sendMessage('Найди DEMO-1', ['attachment-1'])
    assert.equal(reply.text, 'Ответ сервера')
    assert.deepEqual(JSON.parse(calls.find(call => call.url.endsWith('/messages')).options.body), { content: 'Найди DEMO-1', attachment_ids: ['attachment-1'] })
    await uploadAttachment(new File(['test'], 'test.pdf', { type: 'application/pdf' }))
    const upload = calls.find(call => call.url.endsWith('/attachments'))
    assert.ok(upload.options.body instanceof FormData)
    assert.equal(upload.options.headers['Content-Type'], undefined)
    await createOffer(cards[0], 2)
    assert.deepEqual(JSON.parse(calls.find(call => call.url.endsWith('/offers')).options.body), { product_identifier: 'remote-1', article: 'DEMO-1', quantity: 2 })
    assert.equal(calls.filter(call => call.url.endsWith('/confirm')).length, 0)
    const result = await confirmOffer('offer-1', 'fixed-retry-key')
    await confirmOffer('offer-1', 'fixed-retry-key')
    assert.equal(result.outcome, 'cart_unavailable')
    assert.ok(calls.filter(call => call.url.endsWith('/confirm')).every(call => call.options.headers['Idempotency-Key'] === 'fixed-retry-key'))
    assert.equal(calls.filter(call => call.url === '/api/chat/sessions').length, 1)
    await assert.rejects(createOffer(cards[0], 0), /Количество/)
    assert.deepEqual(await history(), {messages: []})
    assert.equal(calls.filter(call => call.url === '/api/chat/sessions').length, 2)
  } finally {
    globalThis.fetch = previousFetch
    if (previousStorage === undefined) delete globalThis.sessionStorage
    else globalThis.sessionStorage = previousStorage
  }
})
