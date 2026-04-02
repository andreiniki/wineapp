"""
scraper.py — Wine Price Watcher România
Caută prin DuckDuckGo HTML + compari.ro + magazine directe.
NU filtrează după volum — extrage și afișează formatul din text.
TVA 21% inclus în prețurile românești.
"""
from __future__ import annotations
import logging, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, unquote, parse_qs, urlparse

import cloudscraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
}

WINE_DOMAINS = [
    "wineshop.ro","vinexpert.ro","king.ro","vinoteca.ro","lavinia.ro",
    "vinmagazin.ro","crushwineshop.ro","vinimondo.ro","winemag.ro","vinia.ro",
    "finestore.ro","indivino.ro","nitelashop.ro","camara-de-vinuri.ro",
    "carpatvinum.ro","smartwines.ro","winepub.ro","cramaerasmus.ro",
    "compari.ro",
]


def parse_ron_price(text: str) -> Optional[float]:
    if not text:
        return None
    t = str(text).strip()
    t = re.sub(r"(\d)\.(\d{3})(?=[,\s\D]|$)", r"\1\2", t)
    t = re.sub(r"(\d) (\d{3})(?=[,\s\D]|$)", r"\1\2", t)
    for p in [
        r"(\d{1,6}[.,]\d{2})\s*(?:lei|ron|RON|Lei|LEI)\b",
        r"(?:lei|ron|RON|Lei|LEI)\s*:?\s*(\d{1,6}[.,]\d{2})",
        r"(\d{2,5})\s*(?:lei|ron|RON|Lei|LEI)\b",
        r'"price"\s*:\s*"?(\d+\.?\d{0,2})"?',
        r"content=[\"'](\d+\.?\d{0,2})[\"']",
    ]:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            try:
                v = float(m.group(1).replace(",", "."))
                if 5.0 <= v <= 50_000.0:
                    return round(v, 2)
            except (ValueError, TypeError):
                pass
    return None


def extract_format(text: str) -> str:
    """Extrage formatul sticlei din text. Returnează string descriptiv."""
    t = text.lower()
    if re.search(r'double\s*magnum|dublu\s*magnum|\b3\s*l\b|\b3[.,]0\s*l|\b3000\s*ml', t):
        return "3L / Double Magnum"
    if re.search(r'\bjeroboam\b', t):
        return "3L / Jeroboam"
    if re.search(r'\bmagnum\b|1[.,]5\s*l|\b1[.,]50\s*l|\b1500\s*ml', t):
        return "1.5L / Magnum"
    if re.search(r'0[.,]75\s*l|\b750\s*ml|\b75\s*cl|\b0\.75\b', t):
        return "0.75L"
    if re.search(r'0[.,]375\s*l|\b375\s*ml|\b37[.,]5\s*cl', t):
        return "0.375L"
    if re.search(r'\b1\s*litru?\b|\b1[.,]0\s*l|\b1000\s*ml', t):
        return "1L"
    if re.search(r'0[.,]5\s*l|\b500\s*ml|\b50\s*cl', t):
        return "0.5L"
    return "—"


def get_domain(url: str) -> str:
    m = re.search(r"(?:https?://)?(?:www\.)?([^/?#\s]+)", url)
    return m.group(1) if m else url


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()[:120]


class WineSearchEngine:

    def __init__(self):
        self._s = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )

    def _fetch(self, url: str, timeout: int = 12) -> Optional[BeautifulSoup]:
        try:
            r = self._s.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return BeautifulSoup(r.content, "lxml")
            logger.debug("HTTP %d: %s", r.status_code, url)
        except Exception as e:
            logger.debug("fetch %s: %s", url, e)
        return None

    # ── 1. compari.ro ─────────────────────────────────────────────────────────

    def _search_compari(self, query: str) -> List[Dict]:
        """
        Caută pe compari.ro — agregator prețuri.
        Metodă: caută produsul, accesează pagina lui și extrage toate ofertele.
        """
        results = []

        # Pasul 1: cauta pe compari.ro
        search_url = f"https://www.compari.ro/cauta/?q={quote_plus(query)}"
        soup = self._fetch(search_url, timeout=15)
        if not soup:
            return []

        # Pasul 2: găsim link-ul primului produs relevant
        product_url = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = href if href.startswith("http") else f"https://www.compari.ro{href}"
            # paginile de produs au /produs/ sau /p/ în URL
            if re.search(r"/produs/|/p/\d", full) and "compari.ro" in full:
                product_url = full
                break

        # Dacă nu găsim /produs/, luăm primul link intern relevant
        if not product_url:
            for a in soup.select("a[href]"):
                href = a["href"]
                if href and not href.startswith("#") and not href.startswith("javascript"):
                    full = href if href.startswith("http") else f"https://www.compari.ro{href}"
                    if "compari.ro" in full and "/cauta" not in full and len(a.get_text(strip=True)) > 5:
                        product_url = full
                        break

        if not product_url:
            # Fallback: parsăm direct pagina de search
            return self._parse_compari_page(soup, search_url, query)

        # Pasul 3: accesăm pagina produsului
        prod_soup = self._fetch(product_url, timeout=15)
        if not prod_soup:
            return self._parse_compari_page(soup, search_url, query)

        return self._parse_compari_page(prod_soup, product_url, query)

    def _parse_compari_page(self, soup: BeautifulSoup, base_url: str, query: str) -> List[Dict]:
        """Parsează o pagină compari.ro și extrage toate ofertele de preț."""
        results = []
        page_text = soup.get_text(separator=" ", strip=True)

        # Numele produsului
        h1 = soup.select_one("h1")
        prod_name = h1.get_text(strip=True) if h1 else query

        fmt = extract_format(prod_name + " " + page_text[:500])

        # Încercăm mai mulți selectori pentru carduri de ofertă
        offer_selectors = [
            ".offer-item", ".oferta", ".shop-offer", ".offer",
            "[class*='offer']", "[class*='shop-item']", "[class*='magazin']",
            "tr[class*='shop']", ".price-row", "[class*='price-row']",
        ]

        offers_found = False
        for sel in offer_selectors:
            offers = soup.select(sel)
            if not offers:
                continue
            for offer in offers[:20]:
                txt = offer.get_text(separator=" ", strip=True)
                price = parse_ron_price(txt)
                if not price:
                    continue
                # Numele magazinului
                shop_el = offer.select_one("img[alt], [class*='shop-name'], [class*='magazin'], a")
                shop = ""
                if shop_el:
                    shop = shop_el.get("alt", "") or shop_el.get_text(strip=True)
                if not shop:
                    shop = get_domain(base_url)
                # Link
                a = offer.select_one("a[href]")
                link = a["href"] if a else base_url
                if link and not link.startswith("http"):
                    link = urljoin(base_url, link)
                results.append({
                    "name": clean_name(prod_name),
                    "price": price,
                    "shop": shop.strip()[:50] or get_domain(base_url),
                    "url": link,
                    "format": fmt,
                })
                offers_found = True

        # Dacă nu am găsit carduri, extragem prețuri din tot textul paginii
        if not offers_found:
            # Căutăm toate pattern-urile preț din pagină
            price_matches = re.findall(
                r"(\d{1,6}[.,]\d{2})\s*(?:lei|ron|RON|Lei|LEI)\b",
                page_text
            )
            for pm in price_matches[:10]:
                v = parse_ron_price(pm + " lei")
                if v:
                    results.append({
                        "name": clean_name(prod_name),
                        "price": v,
                        "shop": "compari.ro",
                        "url": base_url,
                        "format": fmt,
                    })

        return results

    # ── 2. DuckDuckGo HTML ────────────────────────────────────────────────────

    def _search_ddg(self, query: str) -> List[Dict]:
        """Caută pe DuckDuckGo HTML și extrage URL-uri + snippets."""
        items = []
        try:
            q = f"{query} pret lei"
            soup = self._fetch(
                f"https://html.duckduckgo.com/html/?q={quote_plus(q)}&kl=ro-ro",
                timeout=15,
            )
            if not soup:
                return []
            for res in soup.select(".result")[:25]:
                a = res.select_one(".result__a")
                snip_el = res.select_one(".result__snippet")
                if not a:
                    continue
                href = a.get("href", "")
                if "uddg=" in href:
                    try:
                        href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
                    except Exception:
                        continue
                if not href.startswith("http"):
                    continue
                if not any(d in href for d in WINE_DOMAINS):
                    continue
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                items.append({"url": href, "title": a.get_text(strip=True), "snippet": snippet})
        except Exception as e:
            logger.warning("DDG: %s", e)
        return items

    def _fetch_product_page(self, item: Dict) -> Optional[Dict]:
        url = item["url"]
        snippet_price = parse_ron_price(item.get("snippet", "") + " lei")

        soup = self._fetch(url, timeout=12)
        if not soup:
            if snippet_price:
                fmt = extract_format(item.get("title", "") + " " + item.get("snippet", ""))
                return {"name": clean_name(item["title"]), "price": snippet_price,
                        "shop": get_domain(url), "url": url, "format": fmt}
            return None

        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()

        h1 = soup.select_one("h1")
        name = h1.get_text(strip=True) if h1 else item["title"]
        page_text = soup.get_text(separator=" ")
        fmt = extract_format(name + " " + page_text[:500])

        price = None
        for sel in [
            'meta[property="product:price:amount"]', 'meta[itemprop="price"]',
            "span[data-price-type='finalPrice'] .price", ".price-box .price",
            "ins span.woocommerce-Price-amount bdi", "ins .woocommerce-Price-amount",
            "span.woocommerce-Price-amount bdi", "span.woocommerce-Price-amount",
            ".current-price", ".price-new", ".price",
        ]:
            el = soup.select_one(sel)
            if el:
                price = parse_ron_price((el.get("content") or el.get_text()) + " lei")
                if price:
                    break

        if not price:
            price = parse_ron_price(page_text) or snippet_price
        if not price:
            return None

        return {"name": clean_name(name), "price": price,
                "shop": get_domain(url), "url": url, "format": fmt}

    # ── 3. Magazine directe ───────────────────────────────────────────────────

    def _search_direct(self, query: str) -> List[Dict]:
        results = []
        enc = quote_plus(query)
        shop_urls = [
            f"https://king.ro/catalogsearch/result/?q={enc}",
            f"https://vinmagazin.ro/?s={enc}&post_type=product",
            f"https://vinimondo.ro/?s={enc}&post_type=product",
            f"https://www.winemag.ro/?s={enc}&post_type=product",
            f"https://www.crushwineshop.ro/?s={enc}&post_type=product",
            f"https://indivino.ro/?s={enc}&post_type=product",
            f"https://www.finestore.ro/?s={enc}&post_type=product",
        ]

        def scrape(shop_url):
            soup = self._fetch(shop_url)
            if not soup:
                return []
            found = []
            for sel_combo in [
                ("li.item.product,.product-item",
                 ".product-item-name,.product-name,h2,h3",
                 "span[data-price-type='finalPrice'] .price,.price"),
                ("li.product,.woocommerce-loop-product",
                 ".woocommerce-loop-product__title,h2,h3",
                 "ins span.woocommerce-Price-amount bdi,span.woocommerce-Price-amount,.price"),
            ]:
                card_sel, name_sel, price_sel = sel_combo
                for card in soup.select(card_sel)[:10]:
                    ctx = card.get_text(separator=" ", strip=True)
                    n_el = card.select_one(name_sel)
                    p_el = card.select_one(price_sel)
                    if not n_el:
                        continue
                    name = n_el.get_text(strip=True)
                    price = parse_ron_price(p_el.get_text() if p_el else ctx)
                    if not price:
                        continue
                    a = card.select_one("a[href]")
                    link = a["href"] if a else shop_url
                    if link and not link.startswith("http"):
                        link = urljoin(shop_url, link)
                    fmt = extract_format(name + " " + ctx)
                    found.append({"name": clean_name(name), "price": price,
                                  "shop": get_
