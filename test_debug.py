# test_debug.py — pune-l în folderul wineapp și rulează: python3 test_debug.py
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
