"""
scraper.py — Wine Price Watcher România
Strategie: DuckDuckGo HTML → URL-uri produse românești → fetch + extrage preț.
TVA 21% inclus în prețurile afișate. Filtrare strictă 0.75L.
"""
from __future__ import annotations
import logging, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, unquote, parse_qs, urlparse

import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, unquote, parse_qs, urlparse

s = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'windows','desktop':True})
H = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36','Accept-Language':'ro-RO,ro;q=0.9','Referer':'https://duckduckgo.com/'}

WINE_DOMAINS = ["wineshop.ro","vinexpert.ro","king.ro","vinoteca.ro","lavinia.ro",
    "vinmagazin.ro","crushwineshop.ro","vinimondo.ro","winemag.ro","vinia.ro",
    "finestore.ro","indivino.ro","nitelashop.ro"]

print("="*60)
print("TEST 1: DuckDuckGo HTML")
q = "Le Volte Ornellaia 0.75 pret lei"
r = s.get(f"https://html.duckduckgo.com/html/?q={quote_plus(q)}&kl=ro-ro", headers=H, timeout=15)
print(f"Status: {r.status_code}")
soup = BeautifulSoup(r.content, 'lxml')
results = soup.select('.result')
print(f"Rezultate totale DDG: {len(results)}")
wine_found = 0
for res in results[:20]:
    a = res.select_one('.result__a')
    if not a: continue
    href = a.get('href','')
    if 'uddg=' in href:
        try:
            href = unquote(parse_qs(urlparse(href).query).get('uddg',[''])[0])
        except: pass
    is_wine = any(d in href for d in WINE_DOMAINS)
    if is_wine:
        wine_found += 1
        print(f"  ✅ {href}")
    else:
        print(f"  ❌ {href[:70]}")
print(f"URL-uri magazine vin: {wine_found}")

print("\n" + "="*60)
print("TEST 2: king.ro search direct")
r2 = s.get(f"https://king.ro/catalogsearch/result/?q={quote_plus('Le Volte Ornellaia')}", headers=H, timeout=15)
print(f"Status: {r2.status_code}")
soup2 = BeautifulSoup(r2.content, 'lxml')
cards = soup2.select('li.item.product, .product-item')
print(f"Carduri produse găsite: {len(cards)}")
for c in cards[:3]:
    n = c.select_one('.product-item-name, h2, h3')
    print(f"  Produs: {n.get_text()[:60] if n else 'N/A'}")

print("\n" + "="*60)
print("TEST 3: king.ro pagina directa produs")
r3 = s.get("https://king.ro/ornellaia-le-volte-dell-ornellaia-0.750-l.html", headers=H, timeout=15)
print(f"Status: {r3.status_code}")
soup3 = BeautifulSoup(r3.content, 'lxml')
h1 = soup3.select_one('h1')
price = soup3.select_one("span[data-price-type='finalPrice'] .price, .price-box .price, .price")
print(f"H1: {h1.get_text()[:60] if h1 else 'N/A'}")
print(f"Preț: {price.get_text()[:30] if price else 'N/A'}")

print("\n" + "="*60)
print("TEST 4: WooCommerce - vinimondo.ro")
r4 = s.get(f"https://vinimondo.ro/?s={quote_plus('Le Volte Ornellaia')}&post_type=product", headers=H, timeout=15)
print(f"Status: {r4.status_code}")
soup4 = BeautifulSoup(r4.content, 'lxml')
cards4 = soup4.select('li.product, .woocommerce-loop-product')
print(f"Produse găsite: {len(cards4)}")
for c in cards4[:3]:
    n = c.select_one('h2, h3')
    print(f"  Produs: {n.get_text()[:60] if n else 'N/A'}")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
}

WINE_DOMAINS = [
    "wineshop.ro", "vinexpert.ro", "king.ro", "vinoteca.ro",
    "lavinia.ro", "vinmagazin.ro", "crushwineshop.ro", "vinimondo.ro",
    "winemag.ro", "vinia.ro", "finestore.ro", "winepub.ro",
    "indivino.ro", "cramaerasmus.ro", "vinorama.ro", "enoteca.ro",
    "carpatvinum.ro", "smartwines.ro", "nitelashop.ro", "camara-de-vinuri.ro",
]


def parse_ron_price(text: str) -> Optional[float]:
    if not text:
        return None
    t = str(text).strip()
    # elimină separatoare de mii: "1.250,99" → "1250,99"
    t = re.sub(r"(\d)\.(\d{3})(?=[,\s\D]|$)", r"\1\2", t)
    t = re.sub(r"(\d) (\d{3})(?=[,\s\D]|$)", r"\1\2", t)
    patterns = [
        r"(\d{1,6}[.,]\d{2})\s*(?:lei|ron|RON|Lei|LEI)\b",
        r"(?:lei|ron|RON|Lei|LEI)\s*:?\s*(\d{1,6}[.,]\d{2})",
        r"(\d{2,5})\s*(?:lei|ron|RON|Lei|LEI)\b",
        r'"price"\s*:\s*"?(\d+\.?\d{0,2})"?',
        r"content=[\"'](\d+\.?\d{0,2})[\"']",
    ]
    for p in patterns:
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
              r"\b3\s*l\b", r"\b0[.,]375\s*l", r"\b375\s*ml", r"\b0[.,]5\s*l",
              r"\b500\s*ml", r"\b1\s*litru?\b"]:
        if re.search(p, t):
            return False
    for p in [r"0[.,]75\s*l", r"\b750\s*ml", r"\b75\s*cl", r"\b0\.75\b"]:
        if re.search(p, t):
            return True
    return True  # niciun volum menționat → asumăm 0.75L


def get_domain(url: str) -> str:
    m = re.search(r"(?:https?://)?(?:www\.)?([^/?#\s]+)", url)
    return m.group(1) if m else url


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()[:120]


class WineSearchEngine:
    """
    Motor de căutare: DuckDuckGo HTML → URL-uri produse → fetch → preț.
    Paralel: mai multe query-uri simultan.
    """

    def __init__(self):
        self._s = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )

    # ── Fetch simplu ──────────────────────────────────────────────────────────

    def _fetch(self, url: str, timeout: int = 12) -> Optional[BeautifulSoup]:
        try:
            r = self._s.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return BeautifulSoup(r.content, "lxml")
        except Exception as e:
            logger.debug("fetch %s → %s", url, e)
        return None

    # ── DuckDuckGo HTML search ────────────────────────────────────────────────

    def _ddg_urls(self, query: str) -> List[Dict]:
        """
        Caută pe DuckDuckGo HTML și returnează lista de URL-uri
        de pe magazine românești de vinuri, cu snippet.
        """
        found = []
        try:
            q = f"{query} 0.75 pret lei"
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}&kl=ro-ro"
            resp = self._s.get(
                url,
                headers={**HEADERS, "Referer": "https://duckduckgo.com/"},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("DDG returned %d", resp.status_code)
                return []

            soup = BeautifulSoup(resp.content, "lxml")

            for result in soup.select(".result")[:20]:
                a = result.select_one(".result__a")
                snip_el = result.select_one(".result__snippet")
                if not a:
                    continue

                href = a.get("href", "")
                # DDG wraps URLs: /l/?uddg=<encoded>
                if "uddg=" in href:
                    try:
                        params = parse_qs(urlparse(href).query)
                        href = unquote(params.get("uddg", [""])[0])
                    except Exception:
                        continue

                if not href.startswith("http"):
                    continue
                if not any(d in href for d in WINE_DOMAINS):
                    continue

                found.append({
                    "url": href,
                    "title": a.get_text(strip=True),
                    "snippet": snip_el.get_text(strip=True) if snip_el else "",
                })

        except Exception as e:
            logger.warning("DDG search error: %s", e)

        return found

    # ── Extrage preț dintr-o pagină de produs ────────────────────────────────

    def _extract_from_page(self, url: str, fallback_name: str, snippet_price: Optional[float]) -> Optional[Dict]:
        soup = self._fetch(url)
        if not soup:
            # folosim prețul din snippet dacă există
            if snippet_price:
                return {
                    "name": clean_name(fallback_name),
                    "price": snippet_price,
                    "shop": get_domain(url),
                    "url": url,
                    "is_075": True,
                }
            return None

        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()

        # Nume
        h1 = soup.select_one("h1")
        name = h1.get_text(strip=True) if h1 else fallback_name

        # Preț — strategie în cascadă
        price: Optional[float] = None

        # 1. Meta structurate
        for sel in ['meta[property="product:price:amount"]', 'meta[itemprop="price"]']:
            el = soup.select_one(sel)
            if el:
                price = parse_ron_price((el.get("content") or "") + " lei")
                if price:
                    break

        # 2. Selectori comuni
        if not price:
            for sel in [
                "span[data-price-type='finalPrice'] .price",   # Magento (king.ro)
                ".price-box .price",
                "ins span.woocommerce-Price-amount bdi",        # WooCommerce sale
                "ins .woocommerce-Price-amount",
                "span.woocommerce-Price-amount bdi",
                "span.woocommerce-Price-amount",
                ".current-price", ".price-new",
                "[class*='price'][class*='current']",
                "[class*='price'][class*='final']",
                "[class*='price'][class*='sale']",
                ".price",
            ]:
                el = soup.select_one(sel)
                if el:
                    price = parse_ron_price(el.get_text() + " lei")
                    if price:
                        break

        # 3. Fallback: scanăm tot textul
        if not price:
            price = parse_ron_price(soup.get_text(separator=" "))

        # 4. Folosim prețul din snippet
        if not price:
            price = snippet_price

        if not price:
            return None

        ctx = soup.get_text(separator=" ")[:3000]
        return {
            "name": clean_name(name),
            "price": price,
            "shop": get_domain(url),
            "url": url,
            "is_075": is_075_liter(name + " " + ctx),
        }

    # ── Căutare directă pe magazine (fallback) ───────────────────────────────

    def _direct_shop_search(self, query: str) -> List[Dict]:
        """
        Caută direct pe paginile de search ale magazinelor cunoscute.
        Unele shop-uri returnează HTML pur (fără JS) → funcționează.
        """
        results: List[Dict] = []
        encoded = quote_plus(query)

        shop_urls = [
            f"https://king.ro/catalogsearch/result/?q={encoded}+0.75",
            f"https://vinmagazin.ro/?s={encoded}&post_type=product",
            f"https://vinimondo.ro/?s={encoded}&post_type=product",
            f"https://www.winemag.ro/?s={encoded}&post_type=product",
            f"https://www.crushwineshop.ro/?s={encoded}&post_type=product",
            f"https://www.finestore.ro/?s={encoded}&post_type=product",
            f"https://indivino.ro/?s={encoded}&post_type=product",
        ]

        def scrape_shop(shop_url: str) -> List[Dict]:
            soup = self._fetch(shop_url)
            if not soup:
                return []
            found = []

            # Magento
            for card in soup.select("li.item.product, .product-item")[:10]:
                ctx = card.get_text(separator=" ", strip=True)
                name_el = card.select_one(".product-item-name, .product-name, h2, h3")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                price_el = card.select_one("span[data-price-type='finalPrice'] .price, .price")
                price = parse_ron_price(price_el.get_text() if price_el else ctx)
                if not price:
                    continue
                link_el = card.select_one("a[href]")
                url = link_el["href"] if link_el else shop_url
                if url and not url.startswith("http"):
                    url = urljoin(shop_url, url)
                found.append({"name": clean_name(name), "price": price, "shop": get_domain(url), "url": url, "is_075": is_075_liter(name + " " + ctx)})

            # WooCommerce
            for card in soup.select("li.product, .woocommerce-loop-product")[:10]:
                ctx = card.get_text(separator=" ", strip=True)
                name_el = card.select_one(".woocommerce-loop-product__title, h2, h3")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                price_el = (
                    card.select_one("ins span.woocommerce-Price-amount bdi")
                    or card.select_one("span.woocommerce-Price-amount bdi")
                    or card.select_one("span.woocommerce-Price-amount")
                    or card.select_one(".price")
                )
                price = parse_ron_price(price_el.get_text() if price_el else ctx)
                if not price:
                    continue
                link_el = card.select_one("a[href]")
                url = link_el["href"] if link_el else shop_url
                if url and not url.startswith("http"):
                    url = urljoin(shop_url, url)
                found.append({"name": clean_name(name), "price": price, "shop": get_domain(url), "url": url, "is_075": is_075_liter(name + " " + ctx)})

            return found

        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(scrape_shop, u): u for u in shop_urls}
            for fut in as_completed(futures):
                try:
                    results.extend(fut.result(timeout=20))
                except Exception:
                    pass

        return results

    # ── Căutare principală ───────────────────────────────────────────────────

    def search_wine(
        self,
        query: str,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> List[Dict]:
        all_raw: List[Dict] = []

        # ETAPA 1: DuckDuckGo → URL-uri de produse (3 query-uri diferite)
        queries = [
            query,
            f"{query} vin romania",
            f"{query} 0.75L cumpar",
        ]
        ddg_items = []
        for i, q in enumerate(queries):
            ddg_items.extend(self._ddg_urls(q))
            if progress_cb:
                progress_cb(i + 1, 6)
            time.sleep(0.3)

        # deduplicăm URL-urile DDG
        seen_urls: set = set()
        unique_items = []
        for item in ddg_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_items.append(item)

        # ETAPA 2: Fetch fiecare pagină de produs în paralel
        def fetch_item(item: Dict) -> Optional[Dict]:
            snip_price = parse_ron_price(item["snippet"] + " lei") if item.get("snippet") else None
            return self._extract_from_page(item["url"], item["title"], snip_price)

        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(fetch_item, item): item for item in unique_items[:10]}
            done = 0
            for fut in as_completed(futures):
                try:
                    r = fut.result(timeout=20)
                    if r:
                        all_raw.append(r)
                except Exception:
                    pass
                done += 1
                if progress_cb:
                    progress_cb(3 + min(done, 2), 6)

        # ETAPA 3: Fallback — search direct pe magazine
        if len(all_raw) < 3:
            direct = self._direct_shop_search(query)
            all_raw.extend(direct)
            if progress_cb:
                progress_cb(6, 6)

        # Filtrare 0.75L
        filtered = [r for r in all_raw if r.get("is_075", True)]

        # Deduplicare: cel mai mic preț per domeniu
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
