import { useState } from 'react'

const asset = (name: string) => `/reference/${name}`
const money = (amount: number) => `${new Intl.NumberFormat('ru-RU').format(amount)} ₸`

type Product = {
  id: string
  name: string
  sku: string
  category: string
  price: number
  stock: number
  unit: string
  specs: string[]
  art: 'cable' | 'breaker' | 'lamp' | 'tray'
}

type IconName = 'pin' | 'search' | 'menu' | 'compare' | 'heart' | 'cart' | 'chevron' | 'phone' | 'spark' | 'close' | 'arrow'

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const base = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const }
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

const banners = [
  ['Quattro-958x424.png', 'Quattro-313x424.png', 'QUATTRO NEW', 'Розетки/Выключатели/Коробки'],
  ['Kabel-958x424.png', 'Kabel-313x424.png', 'Кабель по ГОСТ', 'Кабель / Провод'],
  ['CHINT-958x424.png', 'CHINT-313x424-_1_.png', 'Низковольтная аппаратура CHINT', 'Низковольтная аппаратура'],
  ['Mufta-958x424-_3_.png', 'Mufta-313x424-_1_.png', 'Муфты ЭРГ Оптима', 'Изделия для монтажа и инструмент'],
  ['958kh424-_-Legrand-_-snizhenie.png', '313kh424-_-Legrand-_-snizhenie.png', 'Legrand', 'Розетки/Выключатели/Коробки'],
  ['KVT_958x424.jpg', 'KVT_313x424.jpg', 'Инструменты КВТ', 'Инструмент / КИП'],
  ['Lotok-958x424.png', 'Lotok-313x424.png', 'Лотки металлические', 'Кабеленесущие системы'],
  ['Promrukav-958x424-_1_.jpg', 'Promrukav-313x424-_1_.jpg', 'Промрукав', 'Изделия для монтажа и инструмент'],
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

export function SiteHeader({ query, cartCount, onQuery, onHome, onCatalog, onCategory, onCart }: {
  query: string
  cartCount: number
  onQuery: (value: string) => void
  onHome: () => void
  onCatalog: () => void
  onCategory: (value: string) => void
  onCart: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [cityOpen, setCityOpen] = useState(false)
  return <header className="ekt-header">
    <div className="ekt-top"><div className="ekt-container ekt-top-inner">
      <button className="ekt-city" onClick={() => setCityOpen(value => !value)}><Icon name="pin" size={17} /> Астана</button>
      <nav className="ekt-top-links" aria-label="Дополнительные ссылки"><a href="https://nursultan.ekt.kz/personal/" target="_blank" rel="noreferrer">Личный кабинет</a><a href="https://pro.ekt.kz/" target="_blank" rel="noreferrer">B2B - EKT PRO</a><a href="https://nursultan.ekt.kz/about/" target="_blank" rel="noreferrer">Покупателям⌄</a><a href="https://nursultan.ekt.kz/about/contacts/" target="_blank" rel="noreferrer">Оставить заявку</a><span>КАЗ</span></nav>
      <div className="ekt-phones"><Icon name="phone" size={18} /><span>+7 (700) 222-05-14<br />+7 (747) 222-05-21</span></div>
      <span className="ekt-demo-label">Демо-витрина</span>
    </div></div>
    <div className="ekt-main-head"><div className="ekt-container ekt-main-inner">
      <button className="ekt-logo" onClick={onHome} aria-label="На главную"><b>EKT</b><small>ЭЛЕКТРОКОМПЛЕКТ</small><em>Демо-витрина</em></button>
      <button className="ekt-catalog-button" aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}>Каталог <Icon name="menu" size={20} /></button>
      <label className="ekt-search"><Icon name="search" size={21} /><input value={query} onChange={event => onQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') onCatalog() }} placeholder="Поиск" aria-label="Поиск товаров" /><span>⌕</span></label>
      <div className="ekt-header-actions"><button title="Сравнение доступно на ekt.kz" disabled><Icon name="compare" /> <span>Сравнить</span></button><button title="Избранное доступно на ekt.kz" disabled><Icon name="heart" /> <span>Избранное</span></button><button onClick={onCart} aria-label={`Корзина, позиций ${cartCount}`}><Icon name="cart" /> <span>Корзина</span><b>{cartCount}</b></button></div>
    </div></div>
    {menuOpen && <div className="ekt-catalog-menu"><div className="ekt-container"><div className="ekt-menu-title"><strong>Каталог продукции</strong><button onClick={() => setMenuOpen(false)} aria-label="Закрыть каталог"><Icon name="close" /></button></div><div className="ekt-menu-grid">{categories.map(([name, picture]) => <button key={name} onClick={() => { onCategory(name); setMenuOpen(false) }}><img src={asset(picture)} alt="" />{name}</button>)}</div></div></div>}
    {cityOpen && <div className="ekt-city-popover"><strong>Ваш город Астана?</strong><div><button onClick={() => setCityOpen(false)}>Да</button><button onClick={() => setCityOpen(false)}>Нет</button></div><small>Выбор города в демонстрации не меняет данные каталога.</small></div>}
  </header>
}

export function HomePage({ onCategory, onAsk }: { onCategory: (value: string) => void; onAsk: () => void }) {
  const [banner, setBanner] = useState(0)
  const [tab, setTab] = useState<'new' | 'sale'>('new')
  const current = banners[banner]
  return <main className="ekt-home">
    <section className="ekt-container ekt-hero" aria-label="Акции и новинки">
      <button className="ekt-hero-main" onClick={() => onCategory(current[3])} aria-label={current[2]}><img src={asset(current[0])} alt={current[2]} /></button>
      <button className="ekt-hero-side" onClick={() => onCategory(current[3])}><img src={asset(current[1])} alt={current[2]} /></button>
      <div className="ekt-hero-mobile-sides">
        <button onClick={() => onCategory('Автоматизация')}><img src={asset('Seminar-313x424-rus.png')} alt="Семинар для электриков" /></button>
        <button onClick={() => onCategory('Кабеленесущие системы')}><img src={asset('Lotok-313x424.png')} alt="Скидки на кабеленесущие системы" /></button>
      </div>
      <button className="ekt-slider-arrow left" onClick={() => setBanner((banner + banners.length - 1) % banners.length)} aria-label="Предыдущий баннер">‹</button>
      <button className="ekt-slider-arrow right" onClick={() => setBanner((banner + 1) % banners.length)} aria-label="Следующий баннер">›</button>
      <div className="ekt-slider-dots">{banners.map((item, index) => <button key={item[0]} className={index === banner ? 'active' : ''} onClick={() => setBanner(index)} aria-label={`Баннер ${index + 1}`} />)}</div>
    </section>
    <section className="ekt-container ekt-home-categories"><h1>Каталог продукции</h1><div className="ekt-category-grid">{categories.map(([name, picture]) => <button key={name} onClick={() => onCategory(name)}><img src={asset(picture)} alt="" /><span>{name}</span></button>)}</div></section>
    <section className="ekt-container ekt-showcase"><div className="ekt-showcase-tabs"><button className={tab === 'new' ? 'active' : ''} onClick={() => setTab('new')}>Новинки</button><button className={tab === 'sale' ? 'active' : ''} onClick={() => setTab('sale')}>Спец предложения</button></div><div className="ekt-showcase-grid">{(tab === 'new' ? showcase : specials).map(([picture, category]) => <button key={picture} onClick={() => onCategory(category)}><span>{tab === 'new' ? 'NEW' : 'АКЦИЯ'}</span><img src={asset(picture)} alt={category} /></button>)}</div></section>
    <section className="ekt-about"><div className="ekt-container"><h2>О компании</h2><div className="ekt-about-row"><img src={asset('main-about.jpg')} alt="Торговый зал Электрокомплект" /><div><p>Группа компаний Электрокомплект — производитель и поставщик электротехнической продукции в Казахстане. Компания выпускает кабельно-проводниковую продукцию, трубы, кабельные каналы и щитовое оборудование.</p><p>Наши магазины и собственные торговые марки представлены в разных городах страны. Мы работаем с производителями электротехники и помогаем подобрать оборудование для задач клиентов.</p><p>Работать с нами удобно, надёжно и выгодно.</p></div></div><div className="ekt-benefits">{[['benefits.png', 'Гарантия Качества'], ['hand.png', 'Оптимальная Цена'], ['nal.png', 'Всегда в наличии'], ['ind.png', 'Индивидуальный подход']].map(([picture, label]) => <div key={label}><img src={asset(picture)} alt="" /><span>{label}</span></div>)}</div></div></section>
    <section className="ekt-more"><h2>Узнать больше</h2><button onClick={onAsk}><Icon name="spark" size={18} /> Спросить ИИ-ассистента</button></section>
  </main>
}

export function CatalogLandingPage({ onHome, onCategory }: { onHome: () => void; onCategory: (value: string) => void }) {
  return <main className="ekt-catalog-landing">
    <div className="ekt-container">
      <h1>Каталог</h1>
      <nav className="ekt-crumbs"><a href="/" onClick={event => { event.preventDefault(); onHome() }}>Главная</a><span>›</span><span>Каталог</span></nav>
      <div className="ekt-category-grid">{categories.map(([name, picture]) => <button key={name} onClick={() => onCategory(name)}><img src={asset(picture)} alt="" /><span>{name}</span></button>)}</div>
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

export function CatalogPage({ products, category, query, inStock, onCategory, onStock, onReset, onHome, onAsk, onProduct }: {
  products: Product[]
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
  const filtered = products.filter(product => (category === 'Все товары' || product.category === category) && (!inStock || product.stock > 0) && (!query || `${product.name} ${product.sku}`.toLowerCase().includes(query.toLowerCase())))
  return <main className="ekt-catalog-page ekt-container"><h1>{category === 'Все товары' ? 'Каталог продукции' : category}</h1><nav className="ekt-crumbs"><a href="/" onClick={event => { event.preventDefault(); onHome() }}>Главная</a><span>›</span><span>Каталог</span>{category !== 'Все товары' && <><span>›</span><span>{category}</span></>}</nav><div className="ekt-catalog-layout"><aside className="ekt-filter"><h2>Фильтр по параметрам</h2><label><span>В наличии</span><input type="checkbox" checked={inStock} onChange={event => onStock(event.target.checked)} /></label><div className="ekt-filter-heading">Категория</div>{['Все товары', ...categories.map(([name]) => name)].map(name => <button key={name} className={name === category ? 'selected' : ''} onClick={() => onCategory(name)}>{name}<Icon name="chevron" size={14} /></button>)}<div className="ekt-filter-actions"><button onClick={onReset}>Сбросить</button></div></aside><div className="ekt-catalog-content"><div className="ekt-catalog-info"><span>Показано товаров: {filtered.length}</span><span>Цены и остатки — демонстрационные</span></div><div className="ekt-catalog-sort"><span>Сортировать⌄</span><button aria-label="Сетка" className="selected">▦</button><button aria-label="Список">☷</button></div><div className="ekt-products">{filtered.map(product => <article key={product.id}><button className="ekt-product-image" onClick={() => onProduct(product, 'info')}><img src={asset(productPictures[product.art])} alt="" /></button><button className="ekt-product-name" onClick={() => onProduct(product, 'info')}>{product.name}</button><div className="ekt-product-price"><small>цена</small><strong>{money(product.price)}</strong></div><div className="ekt-product-meta">Код товара {product.sku}<br />{product.stock ? `В наличии: ${product.stock} ${product.unit}` : 'Нет в наличии'}</div><button className="ekt-buy" onClick={() => onProduct(product, product.stock ? 'add' : 'info')}><Icon name={product.stock ? 'cart' : 'spark'} size={17} /> {product.stock ? 'Купить' : 'Подобрать аналог'}</button></article>)}{!filtered.length && <div className="ekt-no-products"><h3>Товары не найдены</h3><p>Демонстрационный каталог содержит несколько позиций. Спросите ассистента или измените фильтр.</p><button onClick={onAsk}>Спросить ассистента</button></div>}</div></div></div></main>
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
  return <main className="ekt-container ekt-cart-page"><h1>Корзина</h1><div className="ekt-crumbs">Главная <span>›</span> Корзина</div>{remote ? <div className="ekt-cart-empty"><h2>Корзина сервера</h2><p>Ссылка на неё появится после подтверждения товара в чате.</p><button onClick={onAsk}>Открыть ассистента</button></div> : items.length ? <div className="ekt-cart-layout"><div>{items.map(product => <article key={product.id} className="ekt-cart-item"><img src={asset(productPictures[product.art])} alt="" /><div><strong>{product.name}</strong><small>Код товара {product.sku}</small><span>{cart[product.id]} {product.unit} × {money(product.price)}</span><button onClick={() => onRemove(product.id)}>Удалить</button></div><b>{money(cart[product.id] * product.price)}</b></article>)}</div><aside><h2>Ваш заказ</h2><p>Позиций <b>{items.length}</b></p><p>Итого <b>{money(items.reduce((sum, product) => sum + cart[product.id] * product.price, 0))}</b></p><small>Корзина прототипа не связана с ekt.kz. Оформление заказа отключено.</small><button onClick={onCatalog}>Продолжить выбор</button></aside></div> : <div className="ekt-cart-empty"><Icon name="cart" size={132} /><h2>Ваша корзина пуста</h2><p><button className="ekt-cart-return" onClick={onCatalog}>Нажмите здесь</button>, чтобы продолжить покупки.</p></div>}</main>
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
            <input type="email" placeholder="Введите ваш e-mail" aria-label="E-mail" required />
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
          <a href={`${regionSite}/usloviya-po-rassrochke/`}><img src={asset('footer_rassrochka.jpg')} alt="Рассрочка" /></a>
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
      <div className="ekt-footer-copy"><span>© 2020 Группа компаний Электрокомплект · Демонстрационная витрина</span><a href={`${regionSite}/polytic/`}>Политика конфиденциальности</a></div>
    </div></footer>
    <a className="ekt-whatsapp" href={whatsappUrl} target="_blank" rel="noreferrer" aria-label="Открыть WhatsApp Электрокомплект">WhatsApp <img src={asset('whatsapp.svg')} alt="" /></a>
  </>
}
