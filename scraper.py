"""
scraper.py — Motor de căutare prețuri vinuri pentru magazine online din România.

Strategii:
  1. Căutare directă pe fiecare magazin (search endpoint).
  2. DuckDuckGo pentru descoperire de pagini suplimentare.

Toate prețurile sunt cu TVA inclus (prețurile afișate în România includ TVA).
Filtrăm strict sticle 0.75L (750 ml / 75 cl).
"""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from typing import Callable, Dict, List, Optional
from urllib.parse import quote_plus, urljoin

import cloudscraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

WINE_DOMAINS = [
    "wineshop.ro", "vinexpert.ro", "king.ro", "vinoteca.ro",
    "lavinia.ro", "vinmagazin.ro", "crushwineshop.ro", "vinimondo.ro",
    "winemag.ro", "vinia.ro", "finestore.ro", "winepub.ro",
    "cramaerasmus.ro", "vinorama.ro", "enoteca.ro", "vinuri.ro",
    "camara-de-vinuri.ro", "carpatvinum.ro", "smartwines.ro",
]


def parse_ron_price(text: str) -> Optional[float]:
    """
    Extrage prețul în RON din text.
    Acceptă formate: '45,99 lei', '45.99 RON', '249 Lei', 'Lei 45,99',
    '1.250,00 lei', '1 250,99 RON', etc.
    Returnează float sau None.
    """
    if not text:
        return None
    text = str(text).strip()

    # Curățăm separatoarele de mii românești DOAR când sunt urmate de virgulă/spațiu/final
    text_c = re.sub(r"(\d)\.(\d{3})(?=[,\s\D]|$)", r"\1\2", text)
    text_c = re.sub(r"(\d) (\d{3})(?=[,\s\D]|$)", r"\1\2", text_c)

    patterns = [
        r"(?<![.\d])(\d{1,6}[.,]\d{2})\s*(?:lei|ron|RON|Lei|LEI)\b",
        r"(?:lei|ron|RON|Lei|LEI)\s*:?\s*(\d{1,6}[.,]\d{2})(?!\d)",
        r"(?<![.,\d])(\d{2,5})\s*(?:lei|ron|RON|Lei|LEI)\b",
        r'"price"\s*:\s*"?(\d+\.?\d{0,2})"?',
        r'content="(\d+\.?\d{0,2})"',
    ]

    for pattern in patterns:
        for src in (text_c, text):
            m = re.search(pattern, src, re.IGNORECASE)
            if m:
                try:
                    val = float(m.group(1).replace(",", "."))
                    if 5.0 <= val <= 50_000.0:
                        return round(val, 2)
                except (ValueError, TypeError):
                    continue
    return None


def is_075_liter(text: str) -> bool:
    t = str(text).lower()

    excludes = [
        r"1[.,]5\s*l(?:itri?)?",
        r"\b1500\s*ml\b",
        r"\b1\s*500\s*ml\b",
        r"\bmagnum\b",
        r"\bjeroboam\b",
        r"\bdouble\s*magnum\b",
        r"\b3\s*l(?:itri?)?\b",
        r"\b3000\s*ml\b",
        r"\b0[.,]375\s*l",
        r"\b375\s*ml\b",
        r"\b0[.,]5\s*l",
        r"\b500\s*ml\b",
        r"\b1\s*l(?:itru)?\b(?!\s*(?:itri|itres))",
        r"\b1000\s*ml\b",
        r"\b1\s*litru?\b",
    ]
    for pat in excludes:
        if re.search(pat, t):
            return False

    confirms = [
        r"0[.,]75\s*l(?:itri?)?",
        r"\b750\s*ml\b",
        r"\b75\s*cl\b",
        r"\b0\.75\b",
    ]
    for pat in confirms:
        if re.search(pat, t):
            return True

    # Niciun volum menționat → asumăm 0.75L (standard)
    return True


def get_domain(url: str) -> str:
    m = re.search(r"(?:https?://)?(?:www\.)?([^/?#\s]+)", url)
    return m.group(1) if m else url


def clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    return name[:120] if len(name) > 120 else name


class BaseScraper:
    SHOP_NAME: str = "Unknown"

    def __init__(self, session: cloudscraper.CloudScraper):
        self._s = session

    def _fetch(self, url: str, timeout: int = 10) -> Optional[BeautifulSoup]:
        try:
            resp = self._s.get(url, headers=BROWSER_HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return BeautifulSoup(resp.content, "lxml")
            logger.debug("[%s] HTTP %d: %s", self.SHOP_NAME, resp.status_code, url)
        except Exception as exc:
            logger.debug("[%s] Fetch error: %s", self.SHOP_NAME, exc)
        return None

    def _result(self, name: str, price: float, url: str, ctx: str = "") -> Dict:
        return {
            "name": clean_name(name),
            "price": price,
            "shop": self.SHOP_NAME,
            "url": url,
            "is_075": is_075_liter(name + " " + ctx),
        }

    def _parse_cards(
        self,
        soup: BeautifulSoup,
        base_url: str,
        card_sel: str,
        name_sels: List[str],
        price_sels: List[str],
        limit: int = 20,
    ) -> List[Dict]:
        results: List[Dict] = []
        cards = soup.select(card_sel)[:limit]

        for card in cards:
            ctx = card.get_text(separator=" ", strip=True)

            name = ""
            for sel in name_sels:
                el = card.select_one(sel)
                if el:
                    name = el.get("title", "") or el.get_text(strip=True)
                    if len(name) > 3:
                        break
            if not name:
                continue

            price: Optional[float] = None
            for sel in price_sels:
                el = card.select_one(sel)
                if el:
                    raw = el.get("content", "") or el.get_text(strip=True)
                    price = parse_ron_price(raw + " lei")
                    if price:
                        break
            if not price:
                price = parse_ron_price(ctx)
            if not price:
                continue

            link = card.select_one("a[href]")
            prod_url = link["href"] if link and link.get("href") else base_url
            if prod_url and not prod_url.startswith("http"):
                prod_url = urljoin(base_url, prod_url)

            results.append(self._result(name, price, prod_url, ctx))

        return results

    def search(self, query: str) -> List[Dict]:
        raise NotImplementedError


class WineShopScraper(BaseScraper):
    SHOP_NAME = "wineshop.ro"

    def search(self, query: str) -> List[Dict]:
        url = f"https://www.wineshop.ro/cautare?q={quote_plus(query + ' 0.75')}"
        soup = self._fetch(url)
        if not soup:
            return []
        return self._parse_cards(
            soup, url,
            card_sel=".product-item, .col-product, [class*='product-grid-item'], .grid-item",
            name_sels=["h2.product-name", "h3.product-name", ".name", ".product-title", "h2", "h3"],
            price_sels=[".price .value", ".price-box .price", ".price", "[class*='price']"],
        )


class KingRoScraper(BaseScraper):
    SHOP_NAME = "king.ro"

    def search(self, query: str) -> List[Dict]:
        url = f"https://king.ro/catalogsearch/result/?q={quote_plus(query + ' 0.75')}"
        soup = self._fetch(url)
        if not soup:
            return []

        results: List[Dict] = []
        for card in soup.select("li.item.product, .product-item")[:20]:
            ctx = card.get_text(separator=" ", strip=True)
            name_el = card.select_one(".product-item-name, .product-name")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            price_el = card.select_one("span[data-price-type='finalPrice'] .price")
            price = parse_ron_price(price_el.get_text() if price_el else "") or parse_ron_price(ctx)
            if not price:
                continue
            link_el = card.select_one("a.product-item-link, .product-item-name a")
            prod_url = link_el["href"] if link_el and link_el.get("href") else url
            results.append(self._result(name, price, prod_url, ctx))
        return results


class VinexpertScraper(BaseScraper):
    SHOP_NAME = "vinexpert.ro"

    def search(self, query: str) -> List[Dict]:
        for url_tmpl in [
            f"https://vinexpert.ro/search?q={quote_plus(query)}",
            f"https://vinexpert.ro/cautare?q={quote_plus(query)}",
            f"https://vinexpert.ro/?s={quote_plus(query)}&post_type=product",
        ]:
            soup = self._fetch(url_tmpl)
            if not soup:
                continue
            results = self._parse_cards(
                soup, url_tmpl,
                card_sel=".product-item, .product-card, li.product, [class*='product-item']",
                name_sels=[".product-name", ".product-title", "h2", "h3", "[class*='name']"],
                price_sels=[".price", "[class*='price']", "span.amount", ".woocommerce-Price-amount"],
            )
            if results:
                return results
        return []


class VinotecaScraper(BaseScraper):
    SHOP_NAME = "vinoteca.ro"

    def search(self, query: str) -> List[Dict]:
        url = f"https://www.vinoteca.ro/search?q={quote_plus(query)}&type=product"
        soup = self._fetch(url)
        if not soup:
            return []
        return self._parse_cards(
            soup, url,
            card_sel=".grid__item, .product-card, [class*='product'], .card-wrapper",
            name_sels=[".product-card__title", ".card__heading", ".full-unstyled-link", "h3", "h2"],
            price_sels=[
                ".price__sale .price-item--sale",
                ".price-item--regular",
                ".price-item",
                ".price",
            ],
        )


class LaviniaRoScraper(BaseScraper):
    SHOP_NAME = "lavinia.ro"

    def search(self, query: str) -> List[Dict]:
        url = f"https://www.lavinia.ro/search?q={quote_plus(query)}"
        soup = self._fetch(url)
        if not soup:
            return []
        return self._parse_cards(
            soup, url,
            card_sel=".product-miniature, .product-card, [class*='product'], article.product-miniature",
            name_sels=[".product-name", ".product-title", "h2", "h3"],
            price_sels=[".product-price", ".price", "[class*='price']"],
        )


class WooCommerceScraper(BaseScraper):
    def __init__(self, session: cloudscraper.CloudScraper, base_url: str, shop_name: str):
        super().__init__(session)
        self.SHOP_NAME = shop_name
        self._base = base_url.rstrip("/")

    def search(self, query: str) -> List[Dict]:
        url = f"{self._base}/?s={quote_plus(query)}&post_type=product"
        soup = self._fetch(url)
        if not soup:
            return []

        results: List[Dict] = []
        for card in soup.select("li.product, .woocommerce-loop-product, .product")[:20]:
            ctx = card.get_text(separator=" ", strip=True)
            name_el = card.select_one(
                "h2.woocommerce-loop-product__title, "
                ".woocommerce-loop-product__title, "
                "h3.product-title, h2, h3"
            )
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            price_el = (
                card.select_one("ins span.woocommerce-Price-amount bdi")
                or card.select_one("ins .woocommerce-Price-amount")
                or card.select_one("span.woocommerce-Price-amount bdi")
                or card.select_one("span.woocommerce-Price-amount")
                or card.select_one(".price")
            )
            price = parse_ron_price(price_el.get_text() if price_el else "") or parse_ron_price(ctx)
            if not price:
                continue
            link_el = card.select_one("a[href]")
            prod_url = link_el["href"] if link_el and link_el.get("href") else url
            if prod_url and not prod_url.startswith("http"):
                prod_url = urljoin(url, prod_url)
            results.append(self._result(name, price, prod_url, ctx))
        return results


class VinimondoScraper(BaseScraper):
    SHOP_NAME = "vinimondo.ro"

    def search(self, query: str) -> List[Dict]:
        url = f"https://vinimondo.ro/?s={quote_plus(query)}&post_type=product"
        soup = self._fetch(url)
        if not soup:
            return []
        return self._parse_cards(
            soup, url,
            card_sel="li.product, .product, .woocommerce-loop-product",
            name_sels=[".woocommerce-loop-product__title", "h2", "h3"],
            price_sels=["ins span.woocommerce-Price-amount", "span.woocommerce-Price-amount", ".price"],
        )


class WineMagScraper(BaseScraper):
    SHOP_NAME = "winemag.ro"

    def search(self, query: str) -> List[Dict]:
        url = f"https://www.winemag.ro/?s={quote_plus(query)}&post_type=product"
        soup = self._fetch(url)
        if not soup:
            return []
        return self._parse_cards(
            soup, url,
            card_sel="li.product, .product, .woocommerce-loop-product",
            name_sels=[".woocommerce-loop-product__title", "h2", "h3"],
            price_sels=["ins .woocommerce-Price-amount", ".woocommerce-Price-amount", ".price"],
        )


class CrushWineShopScraper(BaseScraper):
    SHOP_NAME = "crushwineshop.ro"

    def search(self, query: str) -> List[Dict]:
        url = f"https://www.crushwineshop.ro/search?q={quote_plus(query)}"
        soup = self._fetch(url)
        if not soup:
            url = f"https://www.crushwineshop.ro/?s={quote_plus(query)}&post_type=product"
            soup = self._fetch(url)
        if not soup:
            return []
        return self._parse_cards(
            soup, url,
            card_sel="li.product, .product, .woocommerce-loop-product, [class*='product-item']",
            name_sels=[".woocommerce-loop-product__title", "h2", "h3", ".product-name"],
            price_sels=["ins .woocommerce-Price-amount", "p.price ins span", "span.woocommerce-Price-amount", ".price"],
        )


class DDGScraper(BaseScraper):
    """Caută pe DuckDuckGo HTML direct, fără librărie externă."""
    SHOP_NAME = "DDG-Discovery"

    def search(self, query: str) -> List[Dict]:
        results: List[Dict] = []
        try:
            from urllib.parse import unquote, parse_qs, urlparse as _urlparse

            search_q = f"{query} 0.75 pret lei"
            ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_q)}"
            resp = self._s.get(
                ddg_url,
                headers={**BROWSER_HEADERS, "Referer": "https://duckduckgo.com/"},
                timeout=15,
            )
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.content, "lxml")

            for result in soup.select(".result")[:15]:
                link_el = result.select_one(".result__a")
                snippet_el = result.select_one(".result__snippet")
                if not link_el:
                    continue

                href = link_el.get("href", "")
                # DuckDuckGo wraps URLs: /l/?uddg=<encoded_url>
                if "uddg=" in href:
                    try:
                        params = parse_qs(_urlparse(href).query)
                        href = unquote(params.get("uddg", [""])[0])
                    except Exception:
                        continue

                if not href.startswith("http"):
                    continue
                if not any(d in href for d in WINE_DOMAINS):
                    continue

                snippet = snippet_el.get_text() if snippet_el else ""
                snippet_price = parse_ron_price(snippet + " lei")

                soup_prod = self._fetch(href, timeout=12)
                if not soup_prod:
                    # folosim prețul din snippet dacă există
                    if snippet_price:
                        name = link_el.get_text(strip=True)
                        results.append({
                            "name": clean_name(name),
                            "price": snippet_price,
                            "shop": get_domain(href),
                            "url": href,
                            "is_075": is_075_liter(name + " " + snippet),
                        })
                    continue

                for tag in soup_prod(["script", "style", "noscript", "header", "footer", "nav"]):
                    tag.decompose()

                h1 = soup_prod.select_one("h1")
                name = h1.get_text(strip=True) if h1 else link_el.get_text(strip=True)

                price: Optional[float] = None
                for sel in [
                    'meta[property="product:price:amount"]',
                    'meta[itemprop="price"]',
                    "span[data-price-type='finalPrice'] .price",
                    ".price-box .price",
                    "ins span.woocommerce-Price-amount bdi",
                    "ins .woocommerce-Price-amount",
                    "span.woocommerce-Price-amount bdi",
                    "span.woocommerce-Price-amount",
                    ".current-price", ".price-new", ".price",
                ]:
                    el = soup_prod.select_one(sel)
                    if el:
                        price = parse_ron_price((el.get("content", "") or el.get_text()) + " lei")
                        if price:
                            break

                if not price:
                    price = parse_ron_price(soup_prod.get_text(separator=" ")) or snippet_price

                if price:
                    ctx = soup_prod.get_text(separator=" ")[:2000]
                    results.append({
                        "name": clean_name(name),
                        "price": price,
                        "shop": get_domain(href),
                        "url": href,
                        "is_075": is_075_liter(name + " " + ctx),
                    })

                time.sleep(0.4)

        except Exception as exc:
            logger.warning("DDGScraper error: %s", exc)

        return results



class WineSearchEngine:
    """
    Motor central care coordonează toți scraperii.
    Returnează DOAR sticle de 0.75L, prețuri cu TVA inclus, sortate după preț.
    """

    _WOOCOMMERCE_SHOPS = [
        ("https://vinmagazin.ro", "vinmagazin.ro"),
        ("https://www.vinia.ro", "vinia.ro"),
        ("https://www.finestore.ro", "finestore.ro"),
        ("https://winepub.ro", "winepub.ro"),
    ]

    MAX_WORKERS = 3
    SCRAPER_TIMEOUT = 20

    def __init__(self):
        self._session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True, "mobile": False}
        )
        self._scrapers = self._build_scrapers()

    def _build_scrapers(self) -> List[BaseScraper]:
        s = self._session
        scrapers: List[BaseScraper] = [
            WineShopScraper(s),
            KingRoScraper(s),
            VinexpertScraper(s),
            VinotecaScraper(s),
            LaviniaRoScraper(s),
            VinimondoScraper(s),
            WineMagScraper(s),
            CrushWineShopScraper(s),
        ]
        for base_url, name in self._WOOCOMMERCE_SHOPS:
            scrapers.append(WooCommerceScraper(s, base_url, name))
        scrapers.append(DDGScraper(s))
        return scrapers

    def search_wine(
        self,
        query: str,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict]:
        all_raw: List[Dict] = []
        total = len(self._scrapers)
        completed = 0

        def run(scraper: BaseScraper) -> List[Dict]:
            try:
                return scraper.search(query)
            except Exception as exc:
                logger.warning("[%s] search error: %s", scraper.SHOP_NAME, exc)
                return []

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as ex:
            future_map = {ex.submit(run, sc): sc for sc in self._scrapers}
            for fut in as_completed(future_map):
                try:
                    all_raw.extend(fut.result(timeout=self.SCRAPER_TIMEOUT))
                except (FuturesTimeout, Exception) as exc:
                    logger.debug("Future error: %s", exc)
                finally:
                    completed += 1
                    if progress_cb:
                        try:
                            progress_cb(completed, total)
                        except Exception:
                            pass

        filtered = [r for r in all_raw if r.get("is_075", True)]

        best: Dict[str, Dict] = {}
        for r in filtered:
            domain = r["shop"]
            if domain not in best or r["price"] < best[domain]["price"]:
                best[domain] = r

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
