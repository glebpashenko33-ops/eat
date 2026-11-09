"""Сквозная проверка сбора через браузер на локальном «магазине».

Сайт отдаёт результаты поиска через собственный JSON-API (цены в копейках),
второй — встраивает их в страницу (__NEXT_DATA__), третий — только через строку поиска.
Нужен Playwright; путь к браузеру можно задать переменной PW_EXECUTABLE."""

import asyncio
import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pw = pytest.importorskip("playwright.async_api")

from collector.catalog import load_products  # noqa: E402
from collector.sources import collect_browser_store  # noqa: E402

GOODS = {
    "гречка ядрица": [{"title": "Гречка ядрица Увелка 800 г", "priceTag": {"price": 8990, "oldPrice": 10990}},
                      {"title": "Хлопья гречневые 400 г", "priceTag": {"price": 7990}}],
    "молоко 2,5%": [{"title": "Молоко Домик в деревне 2,5% 900 мл", "priceTag": {"price": 9490}},
                    {"title": "Молоко сгущённое 380 г", "priceTag": {"price": 12990}}],
    "картофель": [{"title": "Картофель весовой", "priceTag": {"price": 4590}, "unitPrice": 4590}],
}

SPA = """<!doctype html><html><body><input type="search" placeholder="Поиск"><div id=r></div><script>
const q = new URLSearchParams(location.search).get('text');
if (q) fetch('/api/v1/search?q=' + encodeURIComponent(q)).then(r => r.json())
  .then(d => { document.getElementById('r').textContent = d.content.items.map(i => i.title).join(', '); });
</script></body></html>"""

INPUT_ONLY = """<!doctype html><html><body><form action="/found"><input name="q" placeholder="Найти товар"></form></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body: str, ctype: str):
        b = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path == "/api/v1/search":
            self.send(json.dumps({"content": {"items": GOODS.get(qs["q"][0], [])}}), "application/json; charset=utf-8")
        elif u.path in ("/spa/search", "/spa/"):
            self.send(SPA, "text/html; charset=utf-8")
        elif u.path == "/ssr/search":
            items = [{"name": g["title"], "price": g["priceTag"]["price"] / 100} for g in GOODS.get(qs.get("q", [""])[0], [])]
            data = json.dumps({"props": {"pageProps": {"products": items}}}, ensure_ascii=False)
            self.send(f'<html><script id="__NEXT_DATA__" type="application/json">{data}</script></html>', "text/html; charset=utf-8")
        elif u.path in ("/input/", "/input/search"):
            self.send(INPUT_ONLY, "text/html; charset=utf-8")
        elif u.path == "/found":
            self.send(SPA.replace("get('text')", "get('q')"), "text/html; charset=utf-8")
        else:
            self.send_error(404)


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_collect_three_kinds_of_sites(server):
    products = [p for p in load_products() if p["id"] in ("buckwheat", "milk", "potato")]
    stores = {
        "spa": {"name": "SPA", "home": server + "/spa/", "search": server + "/spa/search?text={q}"},
        "ssr": {"name": "SSR", "home": server + "/ssr/", "search": server + "/ssr/search?q={q}"},
        "inp": {"name": "INPUT", "home": server + "/input/", "search": server + "/input/search?x={q}"},
    }

    async def go():
        async with pw.async_playwright() as p:
            exe = os.environ.get("PW_EXECUTABLE") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
            browser = await p.chromium.launch(executable_path=exe)
            ctx = await browser.new_context()
            res = await asyncio.gather(*[collect_browser_store(sid, s, ctx, products, delay=0.05) for sid, s in stores.items()])
            await browser.close()
            return dict(zip(stores, res))

    res = asyncio.run(go())
    for sid in stores:
        got = res[sid]
        assert set(got) == {"buckwheat", "milk", "potato"}, (sid, got)
        assert abs(got["buckwheat"][0].price - 89.90) < 0.01 and got["buckwheat"][0].q == 0.8
        assert abs(got["milk"][0].price - 94.90) < 0.01
        assert got["potato"][0].weighted and abs(got["potato"][0].price - 45.90) < 0.01
