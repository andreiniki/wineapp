"""
scraper.py — Wine Price Watcher România
Sursa principală: compari.ro (agregator)
Fallback: DuckDuckGo HTML → pagini produse
Fără filtru volum — volumul e detectat și afișat ca info.
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

EXCLUDED_DOMAINS = [
    "facebook.com","instagram.com","youtube.com","wikipedia.org",
    "google.com","bing.com","duckduckgo.com","twitter.com","tiktok.com",
    "olx.ro","publi24.ro","okazii.ro","emag.ro","paypal.com",
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


def detect_volume(text: str) -> str:
    """Detectează formatul sticlei din text. Returnează string descriptiv."""
    t = text.lower()
    if re.search(r"dublu\s*magnum|double\s*magnum|\b3\s*l\b|\b3000\s*ml\b", t):
        return "Dublu Magnum (3L)"
    if re.search(r"\bmagnum\b|1[.,]5\s*l|\b1500\s*ml\b", t):
        return "Magnum (1.5L)"
    if re.search(r"\bjeroboam\b|\b3\s*l\b", t):
        return "Jeroboam (3L)"
    if re.search(r"0[.,]75\s*l|\b750\s*ml\b|\b75\s*cl\b", t):
        return "0.75L"
    if re.search(r"0[.,]375\s*l|\b375\s*ml\b", t):
        return "0.375L"
    if re.search(r"\b0[.,]5\s*l|\b500\s*ml\b", t):
        return "0.5L"
    if re.search(r"\b1\s*l(?:itru)?\b|\b1000\s*ml\b", t):
        return "1L"
    return "—"


def get_domain(url: str) -> str:
    m = re.search(r"(?:https?://)?(?:www\.)?([^/?#\s]+)", url)
    return m.group(1) if m else url


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()[:120]


def is_ro_domain(url: str) -> bool:
    domain = get_domain(url)
    if any(e in domain for e in EXCLUDED_DOMAINS):
        return False
    return domain.endswith(".ro")


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

    # ── SURSA 1: compari.ro ───────────────────────────────────────────────────

    def _search_compari(self, query: str) -> List[Dict]:
        results = []

        # Pagina de căutare
        search_url = f"https://www.compari.ro/cauta/?q={quote_plus(query)}"
        soup = self._fetch(search_url)
        if not soup:
            return []

        # Găsim primul link de produs din rezultate
        product_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = urljoin("https://www.compari.ro", href)
            # Paginile de produs pe compari.ro conțin /produs/ sau /p/ în URL
            if "compari.ro" in href and (
                "/produs/" in href or "/p/" in href or "/product/" in href
            ):
                if href not in product_links:
                    product_links.append(href)

        # Dacă nu găsim pagini de produs, luăm prețurile direct din search
        if not product_links:
            results = self._parse_compari_search(soup, search_url)
        else:
            # Accesăm fiecare pagină de produs
            for prod_url in product_links[:5]:
                prod_results = self._parse_compari_product(prod_url, query)
                results.extend(prod_results)
                if results:
                    break  # primul produs cu rezultate e suficient

        return results

    def _parse_compari_search(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extrage prețuri direct din pagina de search compari.ro"""
        results = []
        # Selectori generici pentru carduri de produs
        for card in soup.select(
            ".product-item, .produs-item, .result-item, "
            "[class*='product'], [class*='produs'], [class*='result']"
        )[:20]:
            text = card.get_text(separator=" ", strip=True)
            name_el = card.select_one("h2, h3, .title, .name, [class*='title'], [class*='name']")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue
            price = parse_ron_price(text)
            if not price:
                continue
            link_el = card.select_one("a[href]")
            url = link_el["href"] if link_el else base_url
            if url and not url.startswith("http"):
                url = urljoin(base_url, url)
            results.append({
                "name": clean_name(name),
                "price": price,
                "shop": "compari.ro",
                "url": url,
                "volume": detect_volume(text),
            })
        return results

    def _parse_compari_product(self, prod_url: str, fallback_name: str) -> List[Dict]:
        """Extrage toate ofertele de pe pagina unui produs pe compari.ro"""
        results = []
        soup = self._fetch(prod_url)
        if not soup:
            return []

        h1 = soup.select_one("h1")
        prod_name = h1.get_text(strip=True) if h1 else fallback_name
        page_text = soup.get_text(separator=" ")
        vol = detect_volume(prod_name + " " + page_text[:1000])

        # Ofertele individuale per magazin
        for offer in soup.select(
            ".offer, .oferta, [class*='offer'], [class*='oferta'], "
            ".shop-row, [class*='shop-row'], .price-row, tr"
        )[:30]:
            offer_text = offer.get_text(separator=" ", strip=True)
            price = parse_ron_price(offer_text)
            if not price:
                continue
            # Magazinul sursă
            shop_el = offer.select_one("img[alt], [class*='shop-name'], [class*='magazin']")
            if shop_el:
                shop = shop_el.get("alt", "") or shop_el.get_text(strip=True)
            else:
                shop = "compari.ro"
            shop = shop.strip() or "compari.ro"
            # Link direct la magazin
            link_el = offer.select_one("a[href]")
            offer_url = link_el["href"] if link_el else prod_url
            if offer_url and not offer_url.startswith("http"):
                offer_url = urljoin(prod_url, offer_url)
            results.append({
                "name": clean_name(prod_name),
                "price": price,
                "shop": shop,
                "url": offer_url,
                "volume": vol,
            })

        # Fallback: dacă nu găsim oferte structurate, luăm prețul paginii
        if not results:
            price = parse_ron_price(page_text)
            if price:
                results.append({
                    "name": clean_name(prod_name),
                    "price": price,
                    "shop": "compari.ro",
                    "url": prod_url,
                    "volume": vol,
                })

        return results

    # ── SURSA 2: DuckDuckGo HTML ──────────────────────────────────────────────

    def _search_ddg(self, query: str) -> List[Dict]:
        """DuckDuckGo HTML fără librărie externă, filtrare domenii .ro"""
        results = []
        try:
            q = f"{query} pret lei"
            soup = self._fetch(
                f"https://html.duckduckgo.com/html/?q={quote_plus(q)}&kl=ro-ro"
            )
            if not soup:
                return []

            items = []
            for res in soup.select(".result")[:20]:
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
                if not is_ro_domain(href):
                    continue
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                items.append({"url": href, "title": a.get_text(strip=True), "snippet": snippet})

            # Fetch fiecare pagină de produs
            def fetch_item(item):
                url = item["url"]
                snippet_price = parse_ron_price(item["snippet"] + " lei")
                soup_p = self._fetch(url, timeout=10)
                if not soup_p:
                    if snippet_price:
                        return {"name": clean_name(item["title"]), "price": snippet_price,
                                "shop": get_domain(url), "url": url,
                                "volume": detect_volume(item["snippet"])}
                    return None
                for tag in soup_p(["script", "style", "noscript", "header", "footer", "nav"]):
                    tag.decompose()
                h1 = soup_p.select_one("h1")
                name = h1.get_text(strip=True) if h1 else item["title"]
                price = None
                for sel in [
                    'meta[property="product:price:amount"]', 'meta[itemprop="price"]',
                    "span[data-price-type='finalPrice'] .price", ".price-box .price",
                    "ins span.woocommerce-Price-amount bdi", "ins .woocommerce-Price-amount",
                    "span.woocommerce-Price-amount bdi", "span.woocommerce-Price-amount",
                    ".current-price", ".price-new", ".price",
                ]:
                    el = soup_p.select_one(sel)
                    if el:
                        price = parse_ron_price((el.get("content") or el.get_text()) + " lei")
                        if price:
                            break
                if not price:
                    price = parse_ron_price(soup_p.get_text(separator=" ")) or snippet_price
                if not price:
                    return None
                ctx = name + " " + soup_p.get_text(separator=" ")[:1000]
                return {"name": clean_name(name), "price": price,
                        "shop": get_domain(url), "url": url, "volume": detect_volume(ctx)}

            with ThreadPoolExecutor(max_workers=5) as ex:
                for fut in as_completed({ex.submit(fetch_item, i): i for i in items[:10]}):
                    try:
                        r = fut.result(timeout=18)
                        if r:
                            results.append(r)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("DDG error: %s", e)
        return results

    # ── SURSA 3: magazine directe ─────────────────────────────────────────────

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
            for card_sel, name_sel, price_sel in [
                ("li.item.product,.product-item",
                 ".product-item-name,.product-name,h2,h3",
                 "span[data-price-type='finalPrice'] .price,.price"),
                ("li.product,.woocommerce-loop-product",
                 ".woocommerce-loop-product__title,h2,h3",
                 "ins span.woocommerce-Price-amount bdi,span.woocommerce-Price-amount,.price"),
            ]:
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
                    found.append({"name": clean_name(name), "price": price,
                                  "shop": get_domain(link), "url": link,
                                  "volume": detect_volume(name + " " + ctx)})
            return found

        with ThreadPoolExecutor(max_workers=4) as ex:
            for fut in as_completed({ex.submit(scrape, u): u for u in shop_urls}):
                try:
                    results.extend(fut.result(timeout=20))
                except Exception:
                    pass
        return results

    # ── CĂUTARE PRINCIPALĂ ────────────────────────────────────────────────────

    def search_wine(
        self,
        query: str,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict]:
        all_raw: List[Dict] = []

        if progress_cb: progress_cb(1, 5)
        compari = self._search_compari(query)
        all_raw.extend(compari)

        if progress_cb: progress_cb(2, 5)
        ddg = self._search_ddg(query)
        all_raw.extend(ddg)

        if progress_cb: progress_cb(4, 5)
        if len(all_raw) < 2:
            all_raw.extend(self._search_direct(query))

        if progress_cb: progress_cb(5, 5)

        # Deduplicare: cel mai mic preț per domeniu
        best: Dict[str, Dict] = {}
        for r in all_raw:
            d = r["shop"]
            if d not in best or r["price"] < best[d]["price"]:
                best[d] = r

        return sorted(best.values(), key=lambda x: x["price"])

    def search_multiple(self, queries, progress_cb=None):
        results = {}
        for q in queries:
            results[q] = self.search_wine(q, progress_cb)
            time.sleep(0.5)
        return results
