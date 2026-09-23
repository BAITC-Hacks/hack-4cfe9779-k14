import { useEffect, useRef, useState } from 'react'
import homeContent from './homeContent.json'

const asset = (name: string) => `/reference/${name}`
const money = (amount: number | null) => amount === null ? 'Цена не предоставлена' : `${new Intl.NumberFormat('ru-RU').format(amount)} ₸`

import type { Product } from './api'

type IconName = 'pin' | 'search' | 'menu' | 'compare' | 'heart' | 'cart' | 'chevron' | 'phone' | 'spark' | 'close' | 'arrow' | 'camera'

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const base = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const }
  if (name === 'camera') return <svg {...base}><path d="M8 5 10 2h4l2 3h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" /><circle cx="12" cy="12" r="4" /></svg>
  if (name === 'pin') return <svg {...base}><path d="M12 21s7-6.3 7-12a7 7 0 1 0-14 0c0 5.7 7 12 7 12Z" /><circle cx="12" cy="9" r="2.3" /></svg>
  if (name === 'search') return <svg {...base}><circle cx="10.8" cy="10.8" r="6.7" /><path d="m16 16 5 5" /></svg>
  if (name === 'menu') return <svg {...base}><path d="M4 6h16M4 12h16M4 18h16" /></svg>
  if (name === 'compare') return <svg {...base}><path d="M5 18V9M10 18V5M15 18v-7M20 18v-4" /></svg>
  if (name === 'heart') return <svg {...base}><path d="M20.7 8.3c0 5-8.7 11-8.7 11s-8.7-6-8.7-11a4.4 4.4 0 0 1 8.7-1 4.4 4.4 0 0 1 8.7 1Z" /></svg>
  if (name === 'cart') return <svg {...base}><path d="M3 4h2l2.1 11h11.8l2-8H6" /><circle cx="9" cy="20" r="1" /><circle cx="18" cy="20" r="1" /></svg>
  if (name === 'chevron') return <svg {...base}><path d="m6 9 6 6 6-6" /></svg>
  if (name === 'phone') return <svg {...base}><path d="M7 3H4a2 2 0 0 0-2 2c0 9.4 7.6 17 17 17a2 2 0 0 0 2-2v-3l-5-2-2.1 2.1a15 15 0 0 1-7-7L9 8 7 3Z" /></svg>
  if (name === 'spark') return <svg {...base}><path d="m12 2 2.1 7.9L22 12l-7.9 2.1L12 22l-2.1-7.9L2 12l7.9-2.1L12 2Z" /></svg>
  if (name === 'close') return <svg {...base}><path d="M5 5 19 19M19 5 5 19" /></svg>
  return <svg {...base}><path d="M4 12h16m-6-6 6 6-6 6" /></svg>
}

const categories = [
  ['Кабель / Провод', 'e8452aacec34c99e89fae86202443e1e.png'],
  ['Светильники / Лампы', 'lamps.png'],
  ['Низковольтная аппаратура', 'bc8e282b43e269c3518385316d5cb2b0.png'],
  ['Кабеленесущие системы', '5088ce720b5610802ae30a5bd4ae2365.png'],
  ['Изделия для монтажа и инструмент', 'Group-5.png'],
  ['Прочее оборудование', 'prochee-KIP.png'],
  ['Шкафы / Щиты', 'shchitovoe-oborudovanie.png'],
  ['Розетки/Выключатели/Коробки', 'ustanovochnaya_produktsiya.png'],
  ['Автоматизация', 'avtomatization_icon.png'],
  ['Видеонаблюдение / СКУД / Сигнализация', 'camera_icon.png'],
  ['Инструмент / КИП', 'multimetr_icon.png'],
  ['Корзина Электрика', 'toolbox.jpg'],
] as const

// The original serves a separate mobile template. Both sets of artwork are local.
const banners = [
  ['WhatsApp-Video-2026_09_18-at-13.01.08_FQdP.mp4', 'Seminar-313x424-rus.png', 'Семинар для электриков', 'Автоматизация'],
  ['Lotok-958x424.png', 'Lotok-313x424.png', 'Лотки металлические', 'Кабеленесущие системы'],
  ['Kompozitsiya-1_10_FQdP.mp4', 'TANDEM-313x424.png', 'Прожектор TANDEM', 'Светильники / Лампы'],
  ['Kompozitsiya-1_1-_1__FQdP.mp4', 'TSO-313x424.png', 'Прожекторы TANDEM ORIENT SIGNAL', 'Светильники / Лампы'],
  ['Promrukav-958x424-_1_.jpg', 'Promrukav-313x424-_1_.jpg', 'Монтажные решения Промрукав', 'Изделия для монтажа и инструмент'],
  ['CHINT-958x424.png', 'CHINT-313x424-_1_.png', 'Низковольтная аппаратура CHINT', 'Низковольтная аппаратура'],
  ['Quattro-958x424.png', 'Quattro-313x424.png', 'QUATTRO', 'Розетки/Выключатели/Коробки'],
  ['Kabel-958x424.png', 'Kabel-313x424.png', 'Кабель по ГОСТ', 'Кабель / Провод'],
  ['Mufta-958x424-_3_.png', 'Mufta-313x424-_1_.png', 'Муфты ЭРГ Оптима', 'Изделия для монтажа и инструмент'],
  ['958kh424-_-Legrand-_-snizhenie.png', '313kh424-_-Legrand-_-snizhenie.png', 'Legrand', 'Розетки/Выключатели/Коробки'],
  ['KVT_958x424.jpg', 'KVT_313x424.jpg', 'Инструменты КВТ', 'Инструмент / КИП'],
  ['KVT-rus_FQdP.mp4', 'KVT-instrementy-313x424.png', 'Инструменты КВТ', 'Инструмент / КИП'],
] as const

const showcase = [
  ['Mini_banners_137.jpg', 'Низковольтная аппаратура'],
  ['Mini_banners_135.jpg', 'Изделия для монтажа и инструмент'],
  ['Mini_banners_133.jpg', 'Розетки/Выключатели/Коробки'],
  ['Mini_banners_130.jpg', 'Инструмент / КИП'],
  ['Mini_banners_127.jpg', 'Низковольтная аппаратура'],
] as const

const specials = [
  ['Mini_banners_93.jpg', 'Светильники / Лампы'],
  ['Mini_banners_91.jpg', 'Светильники / Лампы'],
  ['Mini_banners_43.jpg', 'Светильники / Лампы'],
  ['Mini_banners_45.jpg', 'Кабель / Провод'],
  ['Mini_banners_27.jpg', 'Низковольтная аппаратура'],
] as const

const catalogShowcase = [...showcase, ['260x448_ru_konc_iek.png', 'Низковольтная аппаратура']] as const
const catalogSpecials = [...specials, ['260kh448-unit.jpg', 'Изделия для монтажа и инструмент']] as const

type HeaderProps = {
  query: string
  cartCount: number | null
  onQuery: (value: string) => void
  onHome: () => void
  onCatalog: () => void
  onCategory: (value: string) => void
  onCart: () => void
  onAsk: () => void
}

export function SiteHeader({ query, cartCount, onQuery, onHome, onCatalog, onCategory, onCart, onAsk }: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [cityOpen, setCityOpen] = useState(false)
  const search = <div className="ekt-search"><Icon name="search" size={21} /><input value={query} onChange={event => onQuery(event.target.value)} placeholder="Поиск" aria-label="Поиск товаров" /><button onClick={onAsk} aria-label="Поиск по фото через ассистента"><Icon name="camera" size={21} /></button></div>
  const phones = <div className="ekt-phones"><Icon name="phone" size={19} /><div><a href="tel:+77002220514">+7(700) 222-05-14</a><a href="tel:+77472220521">+7(747) 222-05-21</a></div></div>
  return <header className="ekt-header">
    <div className="ekt-top"><div className="ekt-container ekt-top-inner">
      <button className="ekt-city" aria-label="Выбрать город" aria-expanded={cityOpen} onClick={() => setCityOpen(value => !value)}><Icon name="pin" size={18} /><span>Астана</span></button>
      <div className="ekt-mobile-search">{search}</div>
      <nav className="ekt-top-links" aria-label="Дополнительные ссылки"><a href="https://nursultan.ekt.kz/personal/">Личный кабинет</a><a href="https://pro.ekt.kz/">B2B - EKT PRO</a><a href="https://nursultan.ekt.kz/about/">Покупателям <Icon name="chevron" size={16} /></a><a href="https://nursultan.ekt.kz/about/contacts/">Оставить заявку</a><span>КАЗ</span></nav>
      {phones}
      <button className="ekt-mobile-menu" aria-label="Открыть меню" aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}><Icon name="menu" size={27} /></button>
    </div></div>
    <div className="ekt-main-head"><div className="ekt-container ekt-main-inner">
      <button className="ekt-logo" onClick={onHome} aria-label="Электрокомплект — на главную"><img src={asset('logo.svg')} alt="Группа компаний Электрокомплект" /></button>
      <button className="ekt-catalog-button" aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}>Каталог <img src={asset('catalog.svg')} alt="" /></button>
      {search}
      <div className="ekt-header-actions"><a href="https://nursultan.ekt.kz/catalog/compare/"><Icon name="compare" /><span>Сравнить</span></a><a href="https://nursultan.ekt.kz/personal/favorite/"><Icon name="heart" /><span>Избранное</span></a><button onClick={onCart} aria-label={cartCount === null ? 'Корзина сервера' : `Корзина, позиций ${cartCount}`}><img src={asset('cart.svg')} alt="" /><span>Корзина</span>{cartCount !== null && <b>{cartCount}</b>}</button></div>
    </div></div>
    {menuOpen && <div className="ekt-catalog-menu"><div className="ekt-container"><div className="ekt-menu-title"><button onClick={() => { onCatalog(); setMenuOpen(false) }}><strong>Каталог продукции</strong></button><button onClick={() => setMenuOpen(false)} aria-label="Закрыть меню"><Icon name="close" /></button></div><div className="ekt-menu-grid">{categories.map(([name, picture]) => <button key={name} onClick={() => { onCategory(name); setMenuOpen(false) }}><img src={asset(picture)} alt="" />{name}</button>)}</div></div></div>}
    {cityOpen && <div className="ekt-city-popover"><strong>Ваш город Астана?</strong><div><button onClick={() => setCityOpen(false)}>Да</button><button onClick={() => setCityOpen(false)}>Закрыть</button></div><small>В демонстрации доступны данные для Астаны.</small></div>}
  </header>
}

export function MobileNavigation({ cartCount, route, onHome, onCatalog, onCart }: {
  cartCount: number | null; route: string; onHome: () => void; onCatalog: () => void; onCart: () => void
}) {
  return <nav className="ekt-mobile-navigation" aria-label="Основная навигация">
    <button onClick={onHome} aria-current={route === 'home' ? 'page' : undefined}><img src={asset('mobile/icon_home.svg')} alt="" /><span>Главная</span></button>
    <button onClick={onCatalog} aria-current={route === 'catalog' || route === 'products' ? 'page' : undefined}><img src={asset('mobile/icon_catalog.svg')} alt="" /><span>Каталог</span></button>
    <a href="https://pro.ekt.kz/"><img src={asset('mobile/icon_ekt_pro.svg')} alt="" /><span>EKT Pro</span></a>
    <button onClick={onCart} aria-current={route === 'cart' ? 'page' : undefined}><span className="ekt-nav-cart"><img src={asset('mobile/icon_cart.svg')} alt="" />{cartCount !== null && <b>{cartCount}</b>}</span><span>Корзина</span></button>
    <a href="https://nursultan.ekt.kz/personal/"><img src={asset('mobile/icon_user.svg')} alt="" /><span>Личный кабинет</span></a>
  </nav>
}

function CategoryGrid({ onCategory }: { onCategory: (name: string) => void }) {
  return <div className="ekt-category-grid">{categories.map(([name, picture], index) => <button key={name} onClick={() => onCategory(name)}><picture><source media="(max-width: 767px)" srcSet={asset(`mobile/category-${String(index + 1).padStart(2, '0')}.svg`)} /><img src={asset(picture)} alt="" /></picture><span>{name}</span></button>)}</div>
}

function Dots({ count, active, onSelect, label }: { count: number; active: number; onSelect: (index: number) => void; label: string }) {
  return <div className="ekt-dots">{Array.from({ length: count }, (_, index) => <button key={index} className={index === active ? 'active' : ''} onClick={() => onSelect(index)} aria-label={`${label} ${index + 1}`} aria-pressed={index === active} />)}</div>
}

type Slide = { image: string; label: string; action: () => void }
function ImageCarousel({ slides, className = '', initial = 0, desktopInitial }: { slides: Slide[]; className?: string; initial?: number; desktopInitial?: number }) {
  const track = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(initial)
  function select(index: number, behavior: ScrollBehavior = 'smooth') {
    const element = track.current
    const child = element?.children[index] as HTMLElement | undefined
    if (element && child) element.scrollTo({ left: child.offsetLeft - element.offsetLeft, behavior })
  }
  useEffect(() => {
    const mobile = window.matchMedia('(max-width: 767px)')
    const reset = () => select(mobile.matches ? initial : desktopInitial ?? initial, 'instant')
    reset()
    mobile.addEventListener('change', reset)
    return () => mobile.removeEventListener('change', reset)
  }, [initial, desktopInitial])
  return <div className={`ekt-carousel ${className}`}>
    <div ref={track} className="ekt-carousel-track" onScroll={() => {
      const element = track.current
      if (element && element.children.length > 1) {
        const step = (element.children[1] as HTMLElement).offsetLeft - (element.children[0] as HTMLElement).offsetLeft
        const index = Math.round(element.scrollLeft / step)
        setActive(index % slides.length)
        if (index >= slides.length) element.scrollTo({ left: element.scrollLeft - step * slides.length, behavior: 'instant' })
      }
    }}>{[...slides, ...slides.slice(0, 5)].map((slide, index) => <button className="ekt-carousel-slide" key={`${slide.image}-${index}`} tabIndex={index >= slides.length ? -1 : undefined} aria-hidden={index >= slides.length ? true : undefined} onClick={slide.action}><img src={asset(slide.image)} alt={slide.label} loading="lazy" draggable="false" /></button>)}</div>
    <Dots count={slides.length} active={active} onSelect={select} label="Слайд" />
    <div className="ekt-carousel-counter" aria-hidden="true">{slides.length} / {active + 1}</div>
  </div>
}

export function HomePage({ onCategory }: { onCategory: (value: string) => void }) {
  const [banner, setBanner] = useState(2)
  const [paused, setPaused] = useState(false)
  const [tab, setTab] = useState<'new' | 'sale'>('new')
  const current = banners[banner]
  useEffect(() => {
    if (paused || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const timer = window.setInterval(() => setBanner(index => (index + 1) % banners.length), 12000)
    return () => window.clearInterval(timer)
  }, [paused])
  const sideSlides = banners.map(item => ({ image: item[1], label: item[2], action: () => onCategory(item[3]) }))
  const offers = homeContent.offers[tab === 'new' ? 0 : 1]

  return <main className="ekt-home">
    <section className="ekt-container ekt-hero" aria-label="Акции и новинки">
      <div className="ekt-hero-stage" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false) }}>
        <button className="ekt-hero-main" onClick={() => onCategory(current[3])} aria-label={current[2]}>{current[0].endsWith('.mp4') ? <video key={current[0]} src={asset(current[0])} poster={asset(current[0].replace('.mp4', '.jpg'))} autoPlay muted loop playsInline preload="metadata" aria-label={current[2]} /> : <img src={asset(current[0])} alt={current[2]} />}</button>
        <button className="ekt-slider-arrow left" onClick={() => setBanner((banner + banners.length - 1) % banners.length)} aria-label="Предыдущий баннер">‹</button>
        <button className="ekt-slider-arrow right" onClick={() => setBanner((banner + 1) % banners.length)} aria-label="Следующий баннер">›</button>
        <Dots count={banners.length} active={banner} onSelect={setBanner} label="Баннер" />
      </div>
      <ImageCarousel slides={sideSlides} className="ekt-hero-sides" initial={2} desktopInitial={4} />
    </section>
    <section className="ekt-container ekt-home-categories"><h1>Каталог продукции</h1><CategoryGrid onCategory={onCategory} /></section>
    <section className="ekt-container ekt-showcase"><div className="ekt-showcase-tabs" role="tablist" aria-label="Предложения"><button role="tab" aria-selected={tab === 'new'} className={tab === 'new' ? 'active' : ''} onClick={() => setTab('new')}>Новинки</button><button role="tab" aria-selected={tab === 'sale'} className={tab === 'sale' ? 'active' : ''} onClick={() => setTab('sale')}>Спец предложения</button></div><ImageCarousel key={tab} className="ekt-offers-carousel" slides={offers.map(({ image }, index) => ({ image, label: (tab === 'new' ? catalogShowcase : catalogSpecials)[index]?.[1] || 'Новинки электротехники', action: () => onCategory((tab === 'new' ? catalogShowcase : catalogSpecials)[index]?.[1] || 'Все товары') }))} /></section>
    <section className="ekt-about"><div className="ekt-container"><h2>О компании</h2><div className="ekt-about-row"><img src={asset('main-about.jpg')} alt="Торговый зал Электрокомплект" loading="lazy" /><div><p>Группа Компаний Электрокомплект – крупнейший производитель и поставщик электротехнической продукции напряжением до 1кВ на рынке Республики Казахстан. На базе нашей компании эффективно реализуется производство: кабельно-проводниковой продукции, труб ПНД и ПВХ, кабельного канала, производство и сборка щитового оборудования.</p><p>ГК ЭлектроКомплект– это не только точки продаж по всему Казахстану, производство и собственные торговые марки, это также долгосрочное сотрудничество с крупнейшими производителями электротехники.</p><p>Мы несем свет и энергию нашим клиентам, гордимся и ценим то, что делаем для своих клиентов! Работать с нами удобно, надежно и выгодно!</p></div></div><div className="ekt-benefits">{[['benefits.png', 'Гарантия Качества'], ['hand.png', 'Оптимальная Цена'], ['nal.png', 'Всегда в наличии'], ['ind.png', 'Индивидуальный подход']].map(([picture, label]) => <div key={label}><img src={asset(picture)} alt="" loading="lazy" /><span>{label}</span></div>)}</div></div></section>
    <section className="ekt-more"><div className="ekt-container"><h2>Узнать больше</h2><ImageCarousel className="ekt-news-carousel" slides={homeContent.news.map(({ image, url }, index) => ({ image, label: ['Семинар для электриков', 'Монтажные решения Промрукав', 'Новинки CHINT', 'Муфты ЭРГ Оптима'][index] || 'Новости Электрокомплект', action: () => window.location.assign(new URL(url, 'https://nursultan.ekt.kz').href) }))} /></div></section>
  </main>
}

export function CatalogLandingPage({ onHome, onCategory }: { onHome: () => void; onCategory: (value: string) => void }) {
  return <main className="ekt-catalog-landing">
    <div className="ekt-container">
      <h1>Каталог</h1>
      <nav className="ekt-crumbs"><a href="/" onClick={event => { event.preventDefault(); onHome() }}>Главная</a><span>›</span><span>Каталог</span></nav>
      <CategoryGrid onCategory={onCategory} />
    </div>
    <section className="ekt-container ekt-landing-showcase"><h2>Новинки</h2><div className="ekt-showcase-grid ekt-showcase-grid--six">{catalogShowcase.map(([picture, category]) => <button key={picture} onClick={() => onCategory(category)}><span>NEW</span><img src={asset(picture)} alt={category} /></button>)}</div></section>
    <section className="ekt-container ekt-landing-showcase"><h2>Специальные предложения</h2><div className="ekt-showcase-grid ekt-showcase-grid--six">{catalogSpecials.map(([picture, category]) => <button key={picture} onClick={() => onCategory(category)}><img src={asset(picture)} alt={category} /></button>)}</div></section>
  </main>
}

const productPictures: Record<Product['art'], string> = {
  cable: 'e8452aacec34c99e89fae86202443e1e.png',
  breaker: 'bc8e282b43e269c3518385316d5cb2b0.png',
  lamp: 'lamps.png',
  tray: '5088ce720b5610802ae30a5bd4ae2365.png',
}

export function CatalogPage({ products, status, remote, source, page, hasMore, paginated, onPage, category, query, inStock, onCategory, onStock, onReset, onHome, onAsk, onProduct }: {
  products: Product[]
  status: string
  remote: boolean
  source: string
  page: number
  hasMore: boolean
  paginated: boolean
  onPage: (page: number) => void
  category: string
  query: string
  inStock: boolean
  onCategory: (value: string) => void
  onStock: (value: boolean) => void
  onReset: () => void
  onHome: () => void
  onAsk: () => void
  onProduct: (product: Product, action: 'info' | 'add') => void
}) {
  const filtered = products.filter(product => (category === 'Все товары' || product.category === category) && (!inStock || (product.stock ?? 0) > 0) && (remote || !query || `${product.name} ${product.sku}`.toLowerCase().includes(query.toLowerCase())))
  return <main className="ekt-catalog-page ekt-container"><h1>{category === 'Все товары' ? 'Каталог продукции' : category}</h1><nav className="ekt-crumbs"><a href="/" onClick={event => { event.preventDefault(); onHome() }}>Главная</a><span>›</span><span>Каталог</span>{category !== 'Все товары' && <><span>›</span><span>{category}</span></>}</nav><div className="ekt-catalog-layout"><aside className="ekt-filter"><h2>Фильтр по параметрам</h2><label><span>В наличии</span><input type="checkbox" checked={inStock} onChange={event => onStock(event.target.checked)} /></label><div className="ekt-filter-heading">Категория</div>{['Все товары', ...new Set([...categories.map(([name]) => name), ...products.map(product => product.category)])].map(name => <button key={name} className={name === category ? 'selected' : ''} onClick={() => onCategory(name)}>{name}<Icon name="chevron" size={14} /></button>)}<div className="ekt-filter-actions"><button onClick={onReset}>Сбросить</button></div></aside><div className="ekt-catalog-content"><div className="ekt-catalog-info"><span>Показано товаров: {filtered.length}</span><span>{remote ? (source === 'ekt' ? 'Каталог EKT · цены и остатки из API' : 'Серверный демонстрационный каталог') : 'Цены и остатки — демонстрационные'}</span></div><div className="ekt-catalog-sort"><span>Сортировать⌄</span><button aria-label="Сетка" className="selected">▦</button><button aria-label="Список">☷</button></div><div role="status">{status}</div>{paginated && <nav className="catalog-pagination" aria-label="Страницы каталога"><button disabled={page <= 1 || !!status} onClick={() => onPage(page - 1)}>Назад</button><span>Страница {page}</span><button disabled={!hasMore || !!status} onClick={() => onPage(page + 1)}>Далее</button></nav>}<div className="ekt-products">{filtered.map(product => <article key={product.id}><button className="ekt-product-image" onClick={() => onProduct(product, 'info')}><img src={product.imageUrl || asset(productPictures[product.art])} alt="" /></button><button className="ekt-product-name" onClick={() => onProduct(product, 'info')}>{product.name}</button><div className="ekt-product-price"><small>цена</small><strong>{money(product.price)}</strong></div><div className="ekt-product-meta">Код товара {product.sku}<br />{product.stock === null ? 'Наличие не подтверждено' : product.stock ? `В наличии: ${product.stock} ${product.unit}` : 'Нет в наличии'}</div><button className="ekt-buy" onClick={() => onProduct(product, product.stock ? 'add' : 'info')}><Icon name={product.stock ? 'cart' : 'spark'} size={17} /> {product.stock ? 'Купить' : remote ? 'Подробнее' : 'Подобрать аналог'}</button></article>)}{!filtered.length && !status && <div className="ekt-no-products"><h3>Товары не найдены</h3><p>Спросите ассистента или измените фильтр. Прототип показывает ограниченную выборку каталога.</p><button onClick={onAsk}>Спросить ассистента</button></div>}</div></div></div></main>
}

export function CartPage({ products, cart, remote, onRemove, onCatalog, onAsk }: {
  products: Product[]
  cart: Record<string, number>
  remote: boolean
  onRemove: (id: string) => void
  onCatalog: () => void
  onAsk: () => void
}) {
  const items = products.filter(product => cart[product.id])
  return <main className="ekt-container ekt-cart-page"><h1>Корзина</h1><div className="ekt-crumbs">Главная <span>›</span> Корзина</div>{remote ? <div className="ekt-cart-empty"><h2>Корзина EKT не подключена</h2><p>В этой версии бэкенда нет действующего подключения к корзине ekt.kz. Товары не добавляются и заказ не оформляется.</p><button onClick={onAsk}>Открыть ассистента</button></div> : items.length ? <div className="ekt-cart-layout"><div>{items.map(product => <article key={product.id} className="ekt-cart-item"><img src={product.imageUrl || asset(productPictures[product.art])} alt="" /><div><strong>{product.name}</strong><small>Код товара {product.sku}</small><span>{cart[product.id]} {product.unit} × {money(product.price)}</span><button onClick={() => onRemove(product.id)}>Удалить</button></div><b>{money(cart[product.id] * (product.price ?? 0))}</b></article>)}</div><aside><h2>Ваш заказ</h2><p>Позиций <b>{items.length}</b></p><p>Итого <b>{money(items.reduce((sum, product) => sum + cart[product.id] * (product.price ?? 0), 0))}</b></p><small>Корзина прототипа не связана с ekt.kz. Оформление заказа отключено.</small><button onClick={onCatalog}>Продолжить выбор</button></aside></div> : <div className="ekt-cart-empty"><Icon name="cart" size={132} /><h2>Ваша корзина пуста</h2><p><button className="ekt-cart-return" onClick={onCatalog}>Нажмите здесь</button>, чтобы продолжить покупки.</p></div>}</main>
}

const regionSite = 'https://nursultan.ekt.kz'
const whatsappUrl = 'https://api.whatsapp.com/send?phone=77475110521&text=%D0%94%D0%BE%D0%B1%D1%80%D1%8B%D0%B9%20%D0%B4%D0%B5%D0%BD%D1%8C!'
const footerCatalog = [
  [['Спец Предложение', '/catalog/spets_predlozhenie/'], ['Новинки', '/catalog/novinki/'], ['Кабель / Провод', '/catalog/kabel_provod/'], ['Светильники / Лампы', '/catalog/svetilniki_lampy/'], ['Низковольтная аппаратура', '/catalog/nizkovoltnaya_apparatura/']],
  [['Кабеленесущие системы', '/catalog/kabelenesushchie_sistemy/'], ['Изделия для монтажа и инструмент', '/catalog/izdeliya_dlya_montazha_i_instrument/'], ['Прочее оборудование', '/catalog/prochee_oborudovanie/'], ['Шкафы / Щиты', '/catalog/shkafy_shchity/'], ['Розетки/Выключатели/Коробки', '/catalog/rozetki_vyklyuchateli_korobki/']],
  [['Автоматизация', '/catalog/avtomatizatsiya/'], ['Видеонаблюдение / СКУД / Сигнализация', '/catalog/videonablyudenie_skud_signalizatsiya/'], ['Инструмент / КИП', '/catalog/instrument_kip/'], ['Корзина Электрика', '/catalog/korzina_elektrika/']],
] as const

export function SiteFooter() {
  const [note, setNote] = useState(false)
  return <>
    <footer className="ekt-footer"><div className="ekt-container">
      <div className="ekt-footer-main">
        <div className="ekt-newsletter">
          <h3>Подписаться на рассылку</h3>
          <form onSubmit={event => { event.preventDefault(); setNote(true) }}>
            <label className="ekt-email-field"><span>Введите ваш e-mail</span><input type="email" aria-label="E-mail" required /></label>
            <select defaultValue="" aria-label="Кто вы"><option value="" disabled>Укажите, кто Вы?</option><option>Потребитель Физ.лицо</option><option>Электрик</option><option>Торгующая Организация</option><option>Монтажная Организация</option><option>Строительная Организация</option><option>Прочее Юр.лицо</option></select>
            <button>Подписаться</button>
          </form>
          {note && <small>Подписка доступна на официальном сайте nursultan.ekt.kz.</small>}
        </div>
        <div><h3>Группа компаний Электрокомплект</h3><a href={`${regionSite}/about/`}>О компании</a><a href={`${regionSite}/about/our-team/vacancy/`}>Вакансии</a><a href={`${regionSite}/news/`}>Новости</a><a href={`${regionSite}/about/contacts/`}>Контакты</a><a href="https://pro.ekt.kz/">Платформа для бизнеса B2B</a></div>
        <div><h3>Будь с нами</h3><a href={`${regionSite}/personal/`}>Вход/Регистрация</a><a href={`${regionSite}/about/information/`}>Полезная информация</a><a href={`${regionSite}/about/faq/`}>Часто задаваемые вопросы</a><a href={`${regionSite}/about/our-team/`}>Карьера</a><a href={`${regionSite}/cooperation/`}>Сотрудничество</a></div>
        <div><h3>Интернет магазин</h3><a href={`${regionSite}/about/howto/`}>Как сделать заказ?</a><a href={`${regionSite}/checkout-delivery/`}>Доставка и оплата</a><a href={`${regionSite}/return/`}>Условия возврата и обмена</a><a href={`${regionSite}/payments/`}>AirbaPay</a><a href={`${regionSite}/usloviya-po-rassrochke/`}>Условия по рассрочке</a></div>
      </div>
      <div className="ekt-footer-bottom">
        <div className="ekt-footer-media">
          <a href="https://ekt.kz/Cloudpayments/"><img src={asset('cp-visa-mastercard.jpg')} alt="CloudPayments, Visa и Mastercard" /></a>
          <a href={`${regionSite}/usloviya-po-rassrochke/`}><picture><source media="(max-width: 767px)" srcSet={asset('mobile/kaspi_red.png')} /><img src={asset('footer_rassrochka.jpg')} alt="Рассрочка" /></picture></a>
          <div className="ekt-footer-social">
            <a href="https://www.instagram.com/ekt.kz" aria-label="Instagram"><img src={asset('inst.svg')} alt="" /></a>
            <a href="https://www.facebook.com/ekt.kz/" aria-label="Facebook"><img src={asset('fb.svg')} alt="" /></a>
            <a href="https://www.youtube.com/channel/UCpkLMo9LK1xrojY6xni6Vlg" aria-label="YouTube"><img src={asset('youtube.svg')} alt="" /></a>
            <a href={whatsappUrl} aria-label="WhatsApp"><img src={asset('whatsapp.svg')} alt="" /></a>
            <a href={`${regionSite}/3d-tour/`} aria-label="3D тур"><img src={asset('3d.svg')} alt="" /></a>
          </div>
        </div>
        <div className="ekt-footer-catalog"><h3>Группа компаний Электрокомплект</h3><div>{footerCatalog.map((column, index) => <nav key={index}>{column.map(([label, path]) => <a key={path} href={`${regionSite}${path}`}>{label}</a>)}</nav>)}</div></div>
      </div>
      <div className="ekt-footer-copy"><span>© 2020 Группа компаний Электрокомплект</span><a href={`${regionSite}/polytic/`}>Политика конфиденциальности</a></div><small className="ekt-demo-note">Демонстрационная витрина · ИИ-ассистент</small>
    </div></footer>
    <a className="ekt-whatsapp" href={whatsappUrl} target="_blank" rel="noreferrer" aria-label="Открыть WhatsApp Электрокомплект">WhatsApp <img src={asset('whatsapp.svg')} alt="" /></a>
  </>
}
