/// <reference types="vite/client" />
import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import './site.css'
import { CartPage, CatalogLandingPage, CatalogPage, HomePage, MobileNavigation, SiteFooter, SiteHeader } from './Site'

import { apiEnabled, loadCatalogPage, runtimeStatus, type Offer, confirmOffer, createOffer, freshProduct, history, searchCatalog, sendMessage, uploadAttachment, type Product } from './api'

type Proposal = {
  key: string
  id?: string
  productId: string
  name: string
  unit: string
  quantity: number
  maxAvailable?: number
  price?: number
  expiresAt?: string
}

type ChatMessage = {
  role: 'assistant' | 'user'
  text: string
  cards?: Product[]
  proposalKey?: string
  cartUrl?: string
}

const products: Product[] = [
  {
    id: 'cable-vvg-100',
    name: 'Кабель ВВГ 3×2,5 0,66 кВ',
    sku: '05030003',
    category: 'Кабель / Провод',
    price: 780,
    stock: 0,
    unit: 'м',
    specs: ['Медная жила', '3 жилы × 2,5 мм²', 'Напряжение 0,66 кВ'],
    art: 'cable',
    analogId: 'cable-vvg-gost',
  },
  {
    id: 'cable-vvg-gost',
    name: 'Кабель ВВГ 3×2,5 0,66 кВ ГОСТ EKT',
    sku: '05030004',
    category: 'Кабель / Провод',
    price: 802,
    stock: 120,
    unit: 'м',
    specs: ['Медная жила', '3 жилы × 2,5 мм²', 'Напряжение 0,66 кВ'],
    art: 'cable',
  },
  {
    id: 'breaker-c16',
    name: 'Автоматический выключатель 1P C16',
    sku: '06020018',
    category: 'Низковольтная аппаратура',
    price: 1690,
    stock: 24,
    unit: 'шт.',
    specs: ['1 полюс', 'Номинальный ток 16 А', 'Характеристика C'],
    art: 'breaker',
  },
  {
    id: 'lamp-led-18',
    name: 'Светильник LED 18 Вт IP65',
    sku: '04010012',
    category: 'Светильники / Лампы',
    price: 5900,
    stock: 7,
    unit: 'шт.',
    specs: ['Мощность 18 Вт', 'Степень защиты IP65', 'Белый свет'],
    art: 'lamp',
  },
]

const price = (value: number | null) => value === null ? 'Цена не предоставлена' : new Intl.NumberFormat('ru-RU').format(value) + ' ₸'
const safeCartUrl = (value?: string) => {
  if (!value) return undefined
  try {
    const url = new URL(value, window.location.href)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : undefined
  } catch {
    return undefined
  }
}

function Icon({ name, size = 20 }: { name: 'search' | 'cart' | 'send' | 'close' | 'spark' | 'clip' | 'arrow' | 'menu' | 'check' | 'minus' | 'plus'; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const }
  if (name === 'search') return <svg {...common}><circle cx="11" cy="11" r="6.5" /><path d="m16 16 5 5" /></svg>
  if (name === 'cart') return <svg {...common}><path d="M3 4h2l2.2 11h11.7l2-8H6" /><circle cx="9" cy="20" r="1" /><circle cx="18" cy="20" r="1" /></svg>
  if (name === 'send') return <svg {...common}><path d="m3 11 18-8-8 18-2.8-7.2L3 11Z" /><path d="M11 14 21 3" /></svg>
  if (name === 'close') return <svg {...common}><path d="M5 5 19 19M19 5 5 19" /></svg>
  if (name === 'spark') return <svg {...common}><path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2ZM19 17l.6 1.4L21 19l-1.4.6L19 21l-.6-1.4L17 19l1.4-.6L19 17Z" /></svg>
  if (name === 'clip') return <svg {...common}><path d="m8 12.5 6.7-6.7a3 3 0 0 1 4.2 4.2l-8.8 8.8a5 5 0 0 1-7.1-7.1l9.2-9.2" /></svg>
  if (name === 'arrow') return <svg {...common}><path d="M4 12h16m-6-6 6 6-6 6" /></svg>
  if (name === 'menu') return <svg {...common}><path d="M4 6h16M4 12h16M4 18h16" /></svg>
  if (name === 'check') return <svg {...common}><path d="m5 12 4 4L19 6" /></svg>
  if (name === 'minus') return <svg {...common}><path d="M5 12h14" /></svg>
  return <svg {...common}><path d="M5 12h14M12 5v14" /></svg>
}

function ProductArt({ kind, compact = false }: { kind: Product['art']; compact?: boolean }) {
  return <div className={`product-art product-art--${kind}${compact ? ' product-art--compact' : ''}`} aria-hidden="true">
    {kind === 'cable' && <svg viewBox="0 0 240 160"><defs><linearGradient id="cableOuter" x1="0" x2="1"><stop stopColor="#151a20" /><stop offset=".5" stopColor="#424b53" /><stop offset="1" stopColor="#10151b" /></linearGradient></defs><g transform="rotate(-25 120 80)"><rect x="15" y="63" width="132" height="61" rx="20" fill="url(#cableOuter)" /><ellipse cx="147" cy="93" rx="17" ry="31" fill="#89929b" /><ellipse cx="149" cy="93" rx="11" ry="24" fill="#242b31" /><path d="M151 73h74" stroke="#2387c6" strokeWidth="14" strokeLinecap="round" /><path d="M151 93h74" stroke="#d2aa29" strokeWidth="14" strokeLinecap="round" /><path d="M151 113h74" stroke="#7dba5e" strokeWidth="14" strokeLinecap="round" /><path d="M218 73h10M218 93h10M218 113h10" stroke="#b77946" strokeWidth="10" strokeLinecap="round" /></g></svg>}
    {kind === 'breaker' && <svg viewBox="0 0 240 160"><defs><linearGradient id="breakerBody" x1="0" x2="1"><stop stopColor="#f9fafb" /><stop offset="1" stopColor="#d8e0e5" /></linearGradient></defs><g transform="translate(72 15)"><rect x="0" y="0" width="100" height="132" rx="7" fill="url(#breakerBody)" stroke="#b7c3cc" strokeWidth="2" /><rect x="9" y="12" width="82" height="18" rx="2" fill="#eff3f5" /><rect x="15" y="39" width="70" height="52" rx="3" fill="#e8edf1" /><rect x="31" y="43" width="38" height="46" rx="3" fill="#c1cbd3" /><rect x="35" y="46" width="30" height="29" rx="2" fill="#293f51" /><path d="M19 103h62" stroke="#a4b1bc" strokeWidth="2" /><path d="M19 111h48" stroke="#a4b1bc" strokeWidth="2" /><rect x="37" y="121" width="26" height="11" fill="#82929d" /></g></svg>}
    {kind === 'lamp' && <svg viewBox="0 0 240 160"><defs><linearGradient id="lampBody" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#eff4f6" /><stop offset="1" stopColor="#b5c1c9" /></linearGradient></defs><path d="M117 5v41" stroke="#4a5a64" strokeWidth="5" /><rect x="93" y="36" width="48" height="17" rx="5" fill="#4c5e68" /><path d="M71 56h98l21 55c2 6-2 12-8 12H58c-6 0-10-6-8-12l21-55Z" fill="url(#lampBody)" stroke="#9cabba" strokeWidth="2" /><path d="M65 111h110l-9 20H74l-9-20Z" fill="#ebcc65" /><path d="M74 131h92" stroke="#f9e9ad" strokeWidth="8" strokeLinecap="round" /></svg>}
    {kind === 'tray' && <svg viewBox="0 0 240 160"><g transform="rotate(-22 120 80)"><path d="M30 56h185v68H30z" fill="#aab4bc" stroke="#75838d" strokeWidth="3" /><path d="M30 56 46 41h185l-16 15Z" fill="#e4e9eb" stroke="#75838d" strokeWidth="3" /><path d="m215 56 16-15v68l-16 15Z" fill="#87949d" stroke="#75838d" strokeWidth="3" />{[60,91,122,153,184].map(x => <g key={x}><rect x={x} y="70" width="13" height="18" rx="3" fill="#e1e7ea" /><rect x={x} y="98" width="13" height="18" rx="3" fill="#e1e7ea" /></g>)}</g></svg>}
  </div>
}

function readCart(): Record<string, number> {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem('ekt-demo-cart') || '{}')
    if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return {}
    return Object.fromEntries(Object.entries(stored).filter(([id, quantity]) => products.some(p => p.id === id) && Number.isInteger(quantity) && Number(quantity) > 0))
  } catch {
    return {}
  }
}

function findProduct(text: string, activeId?: string) {
  const query = text.toLowerCase().replaceAll('ё', 'е')
  return products.find(p => query.includes(p.sku))
    || (query.includes('автомат') ? products[2] : undefined)
    || (query.includes('светиль') || query.includes('ламп') ? products[3] : undefined)
    || (query.includes('кабел') || query.includes('ввг') ? products[0] : undefined)
    || products.find(p => p.id === activeId)
}

function requestedQuantity(text: string) {
  const value = text.toLowerCase().match(/(?:добавь|добавить|положи)\s+(\d+)/)?.[1]
    || text.toLowerCase().match(/(\d+)\s*(?:шт\.?|штук|метров|метра|м\b)/)?.[1]
  return value ? Math.max(1, Number(value)) : 1
}

type Page = 'home' | 'catalog' | 'products' | 'cart'
const currentPage = (): Page => window.location.hash === '#cart' ? 'cart' : window.location.hash === '#products' ? 'products' : window.location.hash === '#catalog' ? 'catalog' : 'home'

function App() {
  const [route, setRoute] = useState<Page>(currentPage)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('Все товары')
  const [inStock, setInStock] = useState(false)
  const [cart, setCart] = useState<Record<string, number>>(readCart)
  const [remoteCartUrl, setRemoteCartUrl] = useState<string | undefined>()
  const [chatOpen, setChatOpen] = useState(false)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [activeId, setActiveId] = useState<string | undefined>()
  const [pending, setPending] = useState<Proposal | undefined>()
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', text: 'Здравствуйте! Помогу подобрать товар, проверить наличие и найти аналог. Что вас интересует?' }])
  const [catalog, setCatalog] = useState<Product[]>(apiEnabled ? [] : products)
  const [catalogStatus, setCatalogStatus] = useState('')
  const [catalogPage, setCatalogPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [catalogSource, setCatalogSource] = useState('')
  const [connection, setConnection] = useState(apiEnabled ? 'Подключение…' : 'Локальное демо')
  const actionRef = useRef(false)
  const endRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onHash = () => setRoute(currentPage())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => {
    if (!apiEnabled) return
    let cancelled = false
    actionRef.current = true
    setBusy(true)
    Promise.all([history(), runtimeStatus()]).then(([data, status]) => {
      if (cancelled) return
      if (data.messages.length) setMessages(data.messages.map(message => ({ role: message.role, text: message.content })))
      setCatalogSource(status.catalog_source)
      setConnection(status.model_configured ? 'ИИ подключён · прототип' : 'Каталог · без ИИ')
    }).catch(error => {
      if (!cancelled) { setConnection('Нет связи с сервером'); setMessages(current => [...current, { role: 'assistant', text: error.message }]) }
    }).finally(() => { if (!cancelled) { actionRef.current = false; setBusy(false) } })
    return () => { cancelled = true }
  }, [])
  useEffect(() => {
    if (!apiEnabled) return
    const controller = new AbortController()
    setCatalogStatus('Загрузка каталога сервера…')
    setCatalog([])
    const timer = window.setTimeout(() => {
      const search = query.trim() || (category === 'Все товары' ? '' : category)
      const load = search
        ? searchCatalog(search, controller.signal).then(products => ({products, hasMore: false}))
        : loadCatalogPage(catalogPage, controller.signal)
      load.then(result => {
        if (!controller.signal.aborted) { setCatalog(result.products); setHasMore(result.hasMore); setCatalogStatus('') }
      }).catch(error => { if (!controller.signal.aborted) setCatalogStatus(error.message) })
    }, 250)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [query, category, catalogPage])
  useEffect(() => { if (!apiEnabled) localStorage.setItem('ekt-demo-cart', JSON.stringify(cart)) }, [cart])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, pending, chatOpen])
  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setChatOpen(false) }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [])

  const cartCount = apiEnabled ? null : Object.values(cart).filter(Boolean).length
  const append = (...items: ChatMessage[]) => setMessages(current => [...current, ...items])
  const makeProposal = (product: Product, quantity: number) => {
    const available = (product.stock ?? 0) - (cart[product.id] || 0)
    if (available <= 0) {
      append({ role: 'assistant', text: `Товара «${product.name}» сейчас нет в наличии${product.analogId ? '. Могу предложить аналог.' : '.'}`, cards: product.analogId ? [products.find(p => p.id === product.analogId)!] : undefined })
      return
    }
    if (quantity > available) {
      append({ role: 'assistant', text: `Сейчас доступно ${available} ${product.unit}. Укажите количество не больше остатка.` })
      return
    }
    const proposal = { key: crypto.randomUUID(), productId: product.id, name: product.name, unit: product.unit, quantity, maxAvailable: available }
    setPending(proposal)
    setActiveId(product.id)
    append({ role: 'assistant', text: 'Проверьте товар и количество. Корзина изменится только после вашего подтверждения.', proposalKey: proposal.key })
  }

  const openForProduct = (product: Product, action: 'info' | 'add' = 'info') => {
    setChatOpen(true)
    setActiveId(product.id)
    if (apiEnabled) {
      if (action === 'add') void proposeRemote(product, 1)
      else void send(`Расскажи про товар с артикулом ${product.sku}`)
      return
    }
    append({ role: 'user', text: action === 'add' ? `Добавить ${product.name}` : `Расскажи про ${product.name}` })
    if (action === 'add') makeProposal(product, 1)
    else append({ role: 'assistant', text: product.stock ? `В наличии ${product.stock} ${product.unit}. ${product.specs.join('; ')}. Данные и цена в этой витрине демонстрационные.` : `Сейчас нет в наличии. ${product.specs.join('; ')}. Могу показать аналог.`, cards: [product] })
  }

  const showOffer = (offer: Offer, product?: Product) => {
    const proposal = { key: crypto.randomUUID(), id: offer.offer_id, productId: offer.article, name: product?.name || offer.article, unit: product?.unit || '', quantity: offer.quantity, price: Number(offer.price_at_offer), expiresAt: offer.expires_at }
    setPending(proposal)
    append({ role: 'assistant', text: 'Проверьте товар, цену и количество. Для добавления нажмите «Да, добавить».', proposalKey: proposal.key })
  }

  const offerProposal = async (product: Product, quantity: number) => {
    showOffer(await createOffer(product, quantity), product)
  }

  const proposeRemote = async (product: Product, quantity: number) => {
    if (actionRef.current) return
    actionRef.current = true
    setBusy(true)
    setPending(undefined)
    append({ role: 'user', text: `Добавить ${quantity} ${product.unit} «${product.name}»` })
    try { await offerProposal(product, quantity) }
    catch (error) { append({ role: 'assistant', text: error instanceof Error ? error.message : 'Не удалось создать предложение.' }) }
    finally { actionRef.current = false; setBusy(false) }
  }

  const confirm = async () => {
    if (!pending || actionRef.current) return
    actionRef.current = true
    setBusy(true)
    try {
      if (apiEnabled) {
        if (!pending.id) throw new Error('Сервер не передал идентификатор предложения')
        const data = await confirmOffer(pending.id, pending.key)
        if (data.outcome === 'price_changed') {
          const replacement = { ...pending, id: data.offer.offer_id, key: crypto.randomUUID(), quantity: data.offer.quantity, price: Number(data.offer.price_at_offer), expiresAt: data.offer.expires_at }
          setPending(replacement)
          append({ role: 'assistant', text: 'Цена изменилась. Проверьте новое предложение и подтвердите его отдельно.', proposalKey: replacement.key })
          return
        }
        const confirmed = data.outcome === 'confirmed' || data.outcome === 'already_confirmed'
        const cartUrl = confirmed ? safeCartUrl(data.cart_url || undefined) : undefined
        append({ role: 'assistant', text: confirmed ? 'Сервер подтвердил добавление товара.' : (data.outcome === 'cart_unavailable' ? 'Товар не добавлен: корзина EKT пока не подключена.' : `Товар не добавлен. ${data.message}`), cartUrl })
        if (cartUrl) setRemoteCartUrl(cartUrl)
      } else {
        const product = products.find(p => p.id === pending.productId)
        if (!product) throw new Error('Товар не найден')
        const available = (product.stock ?? 0) - (cart[product.id] || 0)
        if (pending.quantity > available) {
          append({ role: 'assistant', text: `Остаток изменился: доступно ${Math.max(0, available)} ${product.unit}. Составьте предложение заново.` })
        } else {
          setCart(current => ({ ...current, [product.id]: (current[product.id] || 0) + pending.quantity }))
          append({ role: 'assistant', text: `Добавлено в демонстрационную корзину: ${pending.quantity} ${product.unit} «${product.name}».`, cartUrl: '#cart' })
        }
      }
      setPending(undefined)
    } catch (error) {
      append({ role: 'assistant', text: error instanceof Error ? error.message : 'Не удалось изменить корзину. Попробуйте ещё раз.' })
    } finally {
      actionRef.current = false
      setBusy(false)
    }
  }

  const send = async (raw = input, attachmentIds?: string[]) => {
    const text = raw.trim()
    if ((!text && !attachmentIds?.length) || actionRef.current) return
    setInput('')
    append({ role: 'user', text: text || 'Отправлено вложение' })
    if (!apiEnabled && /^(да|подтверждаю|да,? добавь)[.!]?$/i.test(text) && pending) { await confirm(); return }
    actionRef.current = true
    setBusy(true)
    setPending(undefined)
    try {
      if (apiEnabled) {
        const data = await sendMessage(text, attachmentIds)
        setConnection('Подключено · прототип')
        append({ role: 'assistant', text: data.text, cards: data.cards })
        if (data.offer) showOffer(data.offer, data.cards.find(card => card.sku === data.offer?.article))
        return
      }
      const lower = text.toLowerCase().replaceAll('ё', 'е')
      const product = findProduct(text, activeId)
      if (product) setActiveId(product.id)
      if (/достав|оплат|минимальн|самовывоз|условия/.test(lower)) {
        append({ role: 'assistant', text: 'Условия оплаты и доставки зависят от города и заказа. Актуальные правила опубликованы на сайте Электрокомплект. Минимальную партию для конкретного товара нужно уточнить по его карточке.', cartUrl: 'https://ekt.kz/checkout-delivery/' })
      } else if (/аналог|замен/.test(lower)) {
        const source = product || products[0]
        const analog = products.find(p => p.id === source.analogId)
        append(analog
          ? { role: 'assistant', text: `Для «${source.name}» подойдёт «${analog.name}»: совпадают тип кабеля, материал жил, число жил, сечение и напряжение. Перед покупкой сравните карточки товаров. В демо доступно ${analog.stock} ${analog.unit}.`, cards: [analog] }
          : { role: 'assistant', text: 'Чтобы подобрать совместимый аналог, укажите артикул или характеристики нужного товара.' })
      } else if (/добав|полож|корзин|купи/.test(lower)) {
        if (!product) append({ role: 'assistant', text: 'Укажите артикул или выберите товар, который хотите добавить.' })
        else makeProposal(product, requestedQuantity(text))
      } else if (/налич|есть|остат/.test(lower)) {
        if (!product) append({ role: 'assistant', text: 'Напишите артикул или название товара — проверю наличие в демонстрационном каталоге.' })
        else append({ role: 'assistant', text: product.stock ? `В демо доступно ${product.stock} ${product.unit} товара «${product.name}».` : `«${product.name}» сейчас нет в наличии в демо. Могу предложить аналог.`, cards: product.stock ? [product] : [product, ...products.filter(p => p.id === product.analogId)] })
      } else if (product) {
        append({ role: 'assistant', text: `${product.name}: ${product.specs.join('; ')}. ${product.stock ? `Доступно ${product.stock} ${product.unit}.` : 'В демо нет в наличии.'} Сертификат в демонстрационных данных не предоставлен.`, cards: [product] })
      } else {
        append({ role: 'assistant', text: 'Напишите артикул, название или характеристики товара. Я помогу проверить наличие, подобрать аналог или объяснить условия покупки.' })
      }
    } catch (error) {
      append({ role: 'assistant', text: error instanceof Error ? error.message : 'Сервис временно недоступен.' })
    } finally {
      actionRef.current = false
      setBusy(false)
    }
  }

  const upload = async (selected?: FileList | null) => {
    const files = Array.from(selected || [])
    if (!files.length || actionRef.current) return
    if (files.length > 5) { append({ role: 'assistant', text: 'Выберите не больше 5 файлов за раз.' }); return }
    if (files.some(file => file.size > 10 * 1024 * 1024)) { append({ role: 'assistant', text: 'Файл слишком большой. Выберите файл до 10 МБ.' }); return }
    const allowed = files.every(file => /\.(pdf|docx|xlsx|jpe?g|png)$/i.test(file.name))
    if (!allowed) { append({ role: 'assistant', text: 'Поддерживаются PDF, DOCX, XLSX, JPEG и PNG.' }); return }
    if (!apiEnabled) {
      append({ role: 'user', text: `📎 ${files.map(file => file.name).join(", ")}` }, { role: 'assistant', text: 'Файл выбран. Распознавание документов появится после подключения Python-бэкенда. Пока попробуйте написать артикул или название текстом.' })
      return
    }
    actionRef.current = true
    setBusy(true)
    setPending(undefined)
    append({ role: 'user', text: `📎 ${files.map(file => file.name).join(", ")}` })
    try {
      const attachments = []
      for (const file of files) attachments.push(await uploadAttachment(file))
      const data = await sendMessage(`Найди товары из файлов: ${files.map(file => file.name).join(', ')}`, attachments.map(item => item.id))
      setConnection('Подключено · прототип')
      append({ role: 'assistant', text: data.text, cards: data.cards })
    } catch (error) {
      append({ role: 'assistant', text: error instanceof Error ? error.message : 'Не удалось обработать файл.' })
    } finally {
      actionRef.current = false
      setBusy(false)
    }
  }

  const navigate = (page: Page) => {
    window.location.hash = page === 'home' ? '' : page
    setRoute(page)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return <>
    <SiteHeader
      onAsk={() => setChatOpen(true)}
      query={query}
      cartCount={cartCount}
      onQuery={value => { setQuery(value); setCategory('Все товары'); if (route !== 'products') navigate('products') }}
      onHome={() => navigate('home')}
      onCatalog={() => navigate('catalog')}
      onCategory={name => { setCategory(name); setQuery(''); navigate('products') }}
      onCart={() => remoteCartUrl ? window.location.assign(remoteCartUrl) : navigate('cart')}
    />
    {route === 'home' ? <HomePage
      onCategory={name => { setCategory(name); setQuery(''); navigate('products') }}
    /> : route === 'catalog' ? <CatalogLandingPage
      onHome={() => navigate('home')}
      onCategory={name => { setCategory(name); setQuery(''); navigate('products') }}
    /> : route === 'products' ? <CatalogPage
      products={catalog}
      status={catalogStatus}
      remote={apiEnabled}
      source={catalogSource}
      page={catalogPage}
      hasMore={hasMore}
      paginated={apiEnabled && !query.trim() && category === 'Все товары'}
      onPage={setCatalogPage}
      category={category}
      query={query}
      inStock={inStock}
      onCategory={setCategory}
      onStock={setInStock}
      onReset={() => { setCategory('Все товары'); setQuery(''); setInStock(false) }}
      onHome={() => navigate('home')}
      onAsk={() => setChatOpen(true)}
      onProduct={openForProduct}
    /> : <CartPage
      products={products}
      cart={cart}
      remote={!!apiEnabled}
      onRemove={id => setCart(current => { const next = { ...current }; delete next[id]; return next })}
      onCatalog={() => navigate('catalog')}
      onAsk={() => { navigate('catalog'); setChatOpen(true) }}
    />}
    <SiteFooter />
    <MobileNavigation route={route} cartCount={cartCount} onHome={() => navigate('home')} onCatalog={() => navigate('catalog')} onCart={() => remoteCartUrl ? window.location.assign(remoteCartUrl) : navigate('cart')} />

    {!chatOpen && <button className="chat-launcher" onClick={() => setChatOpen(true)} aria-label="Открыть ИИ-ассистента"><Icon name="spark" size={26} /><span>Спросить ассистента</span><span className="launcher-pulse" /></button>}
    {chatOpen && <section className="chat-panel" role="dialog" aria-label="ИИ-ассистент"><div className="chat-header"><div className="chat-avatar"><Icon name="spark" size={22} /></div><div><strong>ИИ-ассистент EKT</strong><span><i /> {connection}</span></div><button onClick={() => setChatOpen(false)} aria-label="Закрыть чат"><Icon name="close" size={21} /></button></div><div className="chat-messages" aria-live="polite"><div className="chat-today">Сегодня · консультация по товарам</div>{messages.map((message, index) => <div className={`chat-message chat-message--${message.role}`} key={index}>{message.role === 'assistant' && <div className="message-avatar"><Icon name="spark" size={14} /></div>}<div className="message-content"><div className="message-bubble">{message.text}</div>{message.cards?.map(product => <div className="chat-product" key={product.id}>{product.imageUrl ? <img className="chat-product-photo" src={product.imageUrl} alt="" /> : <ProductArt kind={product.art || 'cable'} compact />}<div><b>{product.name}</b><span>{price(product.price)}</span>{product.sourceUrl && <a href={product.sourceUrl} target="_blank" rel="noreferrer">Карточка EKT</a>}<span>Код {product.sku} · {product.stock === null ? 'наличие не подтверждено' : product.stock ? `${product.stock} ${product.unit} в наличии` : 'нет в наличии'}</span><button onClick={() => openForProduct(product, product.stock ? 'add' : 'info')}>{product.stock ? 'Добавить' : 'Подробнее'} →</button></div></div>)}{pending && message.proposalKey === pending.key && <div className="proposal-card"><b>Подтвердить добавление</b><span>{pending.name}</span>{pending.price !== undefined && <span>Цена: {price(pending.price)}</span>}{pending.expiresAt && <span>Действует до {new Date(pending.expiresAt).toLocaleTimeString()}</span>}<label>Количество {apiEnabled ? <strong>{pending.quantity} {pending.unit}</strong> : <><input type="number" min="1" max={pending.maxAvailable} value={pending.quantity} onChange={event => setPending(current => current && ({ ...current, quantity: Math.max(1, Math.min(current.maxAvailable || 999999, Number(event.target.value) || 1)) }))} /> {pending.unit}</>}</label><div><button className="confirm-button" disabled={busy} onClick={confirm}><Icon name="check" size={17} /> Да, добавить</button><button className="cancel-button" disabled={busy} onClick={() => { setPending(undefined); append({ role: 'assistant', text: 'Добавление отменено. Корзина не изменилась.' }) }}>Отмена</button></div></div>}{message.cartUrl && <a className="cart-link" href={message.cartUrl} onClick={event => { if (message.cartUrl === '#cart') { event.preventDefault(); navigate('cart'); setChatOpen(false) } }}>{message.cartUrl.includes('checkout-delivery') ? 'Условия на ekt.kz' : 'Открыть корзину'} <Icon name="arrow" size={16} /></a>}</div></div>)}{busy && <div className="typing"><span /><span /><span /></div>}<div ref={endRef} /></div><div className="quick-prompts"><button onClick={() => send(apiEnabled ? `Наличие ${activeId || catalog[0]?.sku || ''}` : 'Есть кабель ВВГ 3×2,5?')}>Проверить наличие</button><button onClick={() => send(apiEnabled ? `Подбери аналог ${activeId || catalog[0]?.sku || ''}` : 'Подбери аналог кабеля ВВГ')}>Подобрать аналог</button><button onClick={() => send('Какие условия доставки и оплаты?')}>Доставка и оплата</button></div><form className="chat-composer" onSubmit={event => { event.preventDefault(); void send() }}><input ref={fileRef} className="visually-hidden" type="file" multiple accept=".pdf,.docx,.xlsx,.jpg,.jpeg,.png" onChange={event => { void upload(event.target.files); event.target.value = '' }} /><button type="button" className="attach-button" disabled={busy} onClick={() => fileRef.current?.click()} aria-label="Прикрепить файл"><Icon name="clip" size={21} /></button><input maxLength={4000} value={input} onChange={event => setInput(event.target.value)} placeholder="Напишите вопрос о товаре…" aria-label="Сообщение ассистенту" /><button type="submit" className="send-button" disabled={busy || !input.trim()} aria-label="Отправить сообщение"><Icon name="send" size={19} /></button></form><div className="chat-disclaimer">{catalogSource === 'ekt' ? 'Каталог EKT · цены и остатки из API. Корзина EKT не подключена.' : 'Прототип · демонстрационные данные. Корзина EKT не подключена.'}</div></section>}
  </>
}

createRoot(document.getElementById('root')!).render(<App />)
