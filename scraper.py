"""
scraper.py — Wine Price Watcher România
Sursa principală: compari.ro (agregator prețuri România)
Fallback: DuckDuckGo HTML → pagini produse
TVA 21% inclus. Filtrare 0.75L.
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


def is_075_liter(text: str) -> bool:
    t = text.lower()
    for p in [r"1[.,]5\s*l", r"\b1500\s*ml", r"\bmagnum\b", r"\bjeroboam\b",
              r"\b3\s*l\b", r"\b0[.,]375\s*l", r"\b375\s*ml\b",
              r"\b0[.,]5\s*l", r"\b500\s*ml\b", r"\b1\s*litru?\b"]:
        if re.search(p, t):
            return False
    for p in [r"0[.,]75\s*l", r"\b750\s*ml\b", r"\b75\s*cl\b", r"\b0\.75\b"]:
        if re.search(p, t):
            return True
    return True  # fără volum menționat → 0.75L standard


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
            logger.debug("fetch error %s: %s", url, e)
        return None

    # ── SURSA 1: compari.ro ───────────────────────────────────────────────────

    def _search_compari(self, query: str) -> List[Dict]:
        """
        Caută pe compari.ro — agregator prețuri România.
        Returnează prețuri din toate magazinele găsite.
        """
        results = []
        url = f"https://www.compari.ro/cauta/?q={quote_plus(query)}"
        soup = self._fetch(url)
        if not soup:
            logger.warning("compari.ro inaccesibil")
            return []

        # Fiecare produs găsit pe pagina de rezultate
        for card in soup.select(".product-item, .produs, [class*='product'], .item-produs, article")[:30]:
            text = card.get_text(separator=" ", strip=True)

            # Nume produs
            name_el = card.select_one("h2, h3, .title, .name, [class*='title'], [class*='name']")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name or len(name) < 3:
                continue

            # Preț
            price_el = card.select_one(".price, [class*='price'], .pret, [class*='pret']")
            price = parse_ron_price(price_el.get_text() if price_el else text)
            if not price:
                continue

            # Magazin sursă
            shop_el = card.select_one(".shop, .magazin, [class*='shop'], [class*='magazin'], img[alt]")
            shop = shop_el.get("alt", "") or shop_el.get_text(strip=True) if shop_el else get_domain(url)
            if not shop:
                shop = "compari.ro"

            # Link
            link_el = card.select_one("a[href]")
            prod_url = link_el["href"] if link_el else url
            if prod_url and not prod_url.startswith("http"):
                prod_url = urljoin(url, prod_url)

            results.append({
                "name": clean_name(name),
                "price": price,
                "shop": shop.strip() or "compari.ro",
                "url": prod_url,
                "is_075": is_075_liter(name + " " + text),
            })

        # Dacă pagina de rezultate nu are carduri directe, căutăm pagina produsului
        if not results:
            results = self._search_compari_product_page(query)

        return results

    def _search_compari_product_page(self, query: str) -> List[Dict]:
        """
        Încearcă să acceseze pagina unui produs specific pe compari.ro
        și extrage toate ofertele de preț listate.
        """
        results = []
        # Căutăm link-ul produsului din pagina de search
        search_url = f"https://www.compari.ro/cauta/?q={quote_plus(query)}"
        soup = self._fetch(search_url)
        if not soup:
            return []

        # Primul link de produs
        prod_link = None
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "/produs/" in href or "/p/" in href or "/product/" in href:
                prod_link = href if href.startswith("http") else f"https://www.compari.ro{href}"
                break

        if not prod_link:
            return []

        prod_soup = self._fetch(prod_link)
        if not prod_soup:
            return []

        prod_text = prod_soup.get_text(separator=" ", strip=True)
        h1 = prod_soup.select_one("h1")
        prod_name = h1.get_text(strip=True) if h1 else query

        # Toate ofertele de preț de pe pagina produsului
        for offer in prod_soup.select(".offer, .oferta, .shop-offer, [class*='offer'], [class*='oferta']")[:20]:
            offer_text = offer.get_text(separator=" ", strip=True)
            price = parse_ron_price(offer_text)
            if not price:
                continue
            shop_el = offer.select_one("img[alt], .shop-name, [class*='shop']")
            shop = (shop_el.get("alt") or shop_el.get_text(strip=True)) if shop_el else "compari.ro"
            link_el = offer.select_one("a[href]")
            offer_url = link_el["href"] if link_el else prod_link
            if offer_url and not offer_url.startswith("http"):
                offer_url = urljoin(prod_link, offer_url)
            results.append({
                "name": clean_name(prod_name),
                "price": price,
                "shop": shop.strip() or "compari.ro",
                "url": offer_url,
                "is_075": is_075_liter(prod_name + " " + offer_text),
            })

        return results

    # ── SURSA 2: DuckDuckGo HTML ──────────────────────────────────────────────

    def _search_ddg(self, query: str) -> List[Dict]:
        results = []
        try:
            q = f"{query} 0.75 pret lei"
            soup = self._fetch(
                f"https://html.duckduckgo.com/html/?q={quote_plus(q)}&kl=ro-ro",
            )
            if not soup:
                return []

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
                if not any(d in href for d in WINE_DOMAINS):
                    continue
                snippet = snip_el.get_text(strip=True) if snip_el else ""
                results.append({"url": href, "title": a.get_text(strip=True), "snippet": snippet})
        except Exception as e:
            logger.warning("DDG error: %s", e)
        return results

    def _fetch_product_page(self, item: Dict) -> Optional[Dict]:
        url = item["url"]
        snippet_price = parse_ron_price(item.get("snippet", "") + " lei")

        soup = self._fetch(url, timeout=12)
        if not soup:
            if snippet_price:
                return {"name": clean_name(item["title"]), "price": snippet_price,
                        "shop": get_domain(url), "url": url, "is_075": True}
            return None

        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()

        h1 = soup.select_one("h1")
        name = h1.get_text(strip=True) if h1 else item["title"]

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
            price = parse_ron_price(soup.get_text(separator=" ")) or snippet_price
        if not price:
            return None

        ctx = soup.get_text(separator=" ")[:2000]
        return {"name": clean_name(name), "price": price, "shop": get_domain(url),
                "url": url, "is_075": is_075_liter(name + " " + ctx)}

    # ── SURSA 3: magazine directe ─────────────────────────────────────────────

    def _search_direct(self, query: str) -> List[Dict]:
        results = []
        enc = quote_plus(query)
        urls = [
            f"https://king.ro/catalogsearch/result/?q={enc}",
            f"https://vinmagazin.ro/?s={enc}&post_type=product",
            f"https://vinimondo.ro/?s={enc}&post_type=product",
            f"https://www.winemag.ro/?s={enc}&post_type=product",
            f"https://www.crushwineshop.ro/?s={enc}&post_type=product",
            f"https://indivino.ro/?s={enc}&post_type=product",
        ]

        def scrape(shop_url):
            soup = self._fetch(shop_url)
            if not soup:
                return []
            found = []
            selectors = [
                ("li.item.product, .product-item",
                 ".product-item-name, .product-name, h2, h3",
                 "span[data-price-type='finalPrice'] .price, .price"),
                ("li.product, .woocommerce-loop-product",
                 ".woocommerce-loop-product__title, h2, h3",
                 "ins span.woocommerce-Price-amount bdi, span.woocommerce-Price-amount, .price"),
            ]
            for card_sel, name_sel, price_sel in selectors:
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
                                  "is_075": is_075_liter(name + " " + ctx)})
            return found

        with ThreadPoolExecutor(max_workers=4) as ex:
            for fut in as_completed({ex.submit(scrape, u): u for u in urls}):
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

        # 1. compari.ro — sursa principală
        if progress_cb: progress_cb(1, 5)
        compari = self._search_compari(query)
        all_raw.extend(compari)
        logger.info("compari.ro: %d rezultate", len(compari))

        # 2. DuckDuckGo → pagini produse
        if progress_cb: progress_cb(2, 5)
        ddg_items = self._search_ddg(query)
        if ddg_items:
            with ThreadPoolExecutor(max_workers=5) as ex:
                for fut in as_completed({ex.submit(self._fetch_product_page, i): i for i in ddg_items[:10]}):
                    try:
                        r = fut.result(timeout=20)
                        if r:
                            all_raw.append(r)
                    except Exception:
                        pass
        logger.info("DDG: %d rezultate", len(all_raw) - len(compari))

        # 3. Magazine directe (fallback dacă < 2 rezultate)
        if progress_cb: progress_cb(4, 5)
        if len(all_raw) < 2:
            direct = self._search_direct(query)
            all_raw.extend(direct)
            logger.info("direct shops: %d rezultate", len(direct))

        if progress_cb: progress_cb(5, 5)

        # Filtrare 0.75L
        filtered = [r for r in all_raw if r.get("is_075", True)]

        # Cel mai mic preț per domeniu
        best: Dict[str, Dict] = {}
        for r in filtered:
            d = r["shop"]
            if d not in best or r["price"] < best[d]["price"]:
                best[d] = r

        return sorted(best.values(), key=lambda x: x["price"])

    def search_multiple(
        self,
        queries: List[str],
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, List[Dict]]:
        results: Dict[str, List[Dict]] = {}
        for q in queries:
            results[q] = self.search_wine(q, progress_cb)
            time.sleep(0.5)
        return results
