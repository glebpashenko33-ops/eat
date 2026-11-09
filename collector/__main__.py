"""Сборщик живых цен продуктовых сетей.

  python -m collector setup                 — открыть сайты сетей и выбрать свой адрес/магазин (один раз)
  python -m collector collect               — собрать цены во всех сетях -> web/data/prices.json
  python -m collector collect --stores magnit,lenta --limit 5
  python -m collector collect --api-only    — только прямой API Магнита, без браузера (так работает GitHub Actions)
  python -m collector diagnose lenta "молоко" — показать, что сайт отдаёт на запрос (для отладки)
  python -m collector serve                 — открыть приложение: http://<IP компьютера>:8080 с телефона в той же Wi-Fi
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import json
import logging
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

from .catalog import ROOT, Offer, load_products
from .sources import collect_browser_store, collect_magnit_api, load_config, BrowserStore

PRICES_PATH = ROOT / "web" / "data" / "prices.json"
PROFILE_DIR = ROOT / ".browser-profile"
log = logging.getLogger("collector")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── prices.json ──

def merge_prices(path: Path, results: dict[str, dict[str, list[Offer]]], method: dict[str, str], names: dict[str, str]) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    data.setdefault("stores", {})
    data.setdefault("items", {})
    for sid, found in results.items():
        if not found:
            log.warning("%s: цен не получено — оставляю прежние данные", names.get(sid, sid))
            continue
        for per_store in data["items"].values():
            per_store.pop(sid, None)
        for pid, offers in found.items():
            data["items"].setdefault(pid, {})[sid] = [o.to_json() for o in offers]
        data["stores"][sid] = {"name": names.get(sid, sid), "updated": now_iso(), "found": len(found), "method": method[sid]}
    data["items"] = {k: v for k, v in sorted(data["items"].items()) if v}
    data["updated"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


# ── Браузер ──

async def open_browser(args):
    from playwright.async_api import async_playwright  # импорт здесь: для --api-only браузер не нужен

    pw = await async_playwright().start()
    kw = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=args.headless,
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        viewport={"width": 1366, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    if args.executable:
        kw["executable_path"] = args.executable
    elif args.browser in ("msedge", "chrome"):
        kw["channel"] = args.browser
    ctx = await pw.chromium.launch_persistent_context(**kw)
    return pw, ctx


def default_browser() -> str:
    return "msedge" if sys.platform == "win32" else "chromium"


def pick_stores(cfg: dict, arg: str | None) -> dict[str, dict]:
    stores = cfg["stores"]
    if not arg:
        return dict(stores)
    out = {}
    for sid in arg.split(","):
        sid = sid.strip()
        if sid not in stores:
            raise SystemExit(f"Неизвестная сеть «{sid}». Есть: {', '.join(stores)}")
        out[sid] = stores[sid]
    return out


def pick_products(args) -> list[dict]:
    products = load_products()
    if args.products:
        want = set(args.products.split(","))
        products = [p for p in products if p["id"] in want]
    if args.limit:
        products = products[: args.limit]
    return products


async def cmd_collect(args) -> int:
    cfg = load_config()
    stores = pick_stores(cfg, args.stores)
    products = pick_products(args)
    names = {sid: s["name"] for sid, s in cfg["stores"].items()}
    results: dict[str, dict[str, list[Offer]]] = {}
    method: dict[str, str] = {}

    if args.api_only:
        if "magnit" not in stores:
            raise SystemExit("--api-only умеет только Магнит")
        results["magnit"] = await asyncio.to_thread(collect_magnit_api, products, cfg["magnit_api"])
        method["magnit"] = "api"
    else:
        pw, ctx = await open_browser(args)
        try:
            tasks = {sid: collect_browser_store(sid, s, ctx, products, args.delay) for sid, s in stores.items()}
            done = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for sid, res in zip(tasks, done):
                if isinstance(res, Exception):
                    log.error("%s: сбор упал: %s", names[sid], res)
                    res = {}
                results[sid] = res
                method[sid] = "browser"
        finally:
            await ctx.close()
            await pw.stop()
        # Магнит: если сайт не отдал цены, пробуем прямой API
        if "magnit" in stores and not results.get("magnit"):
            log.info("Магнит: пробую прямой API")
            results["magnit"] = await asyncio.to_thread(collect_magnit_api, products, cfg["magnit_api"])
            method["magnit"] = "api"

    data = merge_prices(Path(args.out), results, method, names)
    print("\nИтог:")
    for sid in stores:
        n = len(results.get(sid) or {})
        print(f"  {names[sid]:<12} {n:>3}/{len(products)} продуктов" + ("" if n else "  ← не удалось, см. сообщения выше"))
    print(f"Цены сохранены: {args.out} (сетей с ценами: {len(data['stores'])})")
    return 0 if any(results.values()) else 1


async def cmd_setup(args) -> int:
    cfg = load_config()
    stores = pick_stores(cfg, args.stores)
    args.headless = False
    pw, ctx = await open_browser(args)
    for s in stores.values():
        page = await ctx.new_page()
        try:
            await page.goto(s["home"], wait_until="domcontentloaded", timeout=60000)
        except Exception as e:  # noqa: BLE001
            print(f"{s['name']}: не открылся ({e})")
    for p in ctx.pages:
        if p.url == "about:blank" and len(ctx.pages) > 1:
            await p.close()
    print("\nВ открывшемся браузере на каждой вкладке выберите свой город и адрес (магазин),\n"
          "при необходимости пройдите проверку «я не робот».\n"
          "Когда закончите — просто закройте окно браузера. Выбор сохранится для сбора цен.")
    closed = asyncio.get_running_loop().create_future()
    ctx.on("close", lambda *_: closed.done() or closed.set_result(True))
    await closed
    await pw.stop()
    print("Готово. Теперь: python -m collector collect")
    return 0


async def cmd_diagnose(args) -> int:
    cfg = load_config()
    store = pick_stores(cfg, args.store)[args.store]
    pw, ctx = await open_browser(args)
    page = await ctx.new_page()
    seen = []
    page.on("response", lambda r: seen.append((r.status, r.headers.get("content-type", ""), r.url)))
    bs = BrowserStore(args.store, store, page, wait_ms=5000)
    cands = await bs.search(args.query)
    print(f"\nОткрыта страница: {page.url}")
    print("JSON-ответы сайта:")
    for st, ct, url in seen:
        if "json" in ct:
            print(f"  {st} {url[:150]}")
    print(f"\nНайдено товаров с ценой: {len(cands)}")
    for c in cands[:25]:
        print(f"  {c['prices']}  {c.get('unit_price') or ''}  {c['name'][:80]}")
    shot = ROOT / f"diagnose-{args.store}.png"
    await page.screenshot(path=str(shot), full_page=False)
    print(f"Снимок страницы: {shot}")
    await ctx.close()
    await pw.stop()
    return 0


def lan_ips() -> list[str]:
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *a):  # тише в консоли
        pass


def cmd_serve(args) -> int:
    handler = functools.partial(NoCacheHandler, directory=str(ROOT / "web"))
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"Приложение запущено:\n  на этом компьютере: http://localhost:{args.port}")
    for ip in lan_ips():
        print(f"  с телефона в той же Wi-Fi: http://{ip}:{args.port}")
    print("Остановить: Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m collector", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def browser_opts(p):
        p.add_argument("--browser", default=default_browser(), choices=["msedge", "chrome", "chromium"],
                       help="какой браузер использовать (по умолчанию Edge на Windows)")
        p.add_argument("--executable", help="путь к исполняемому файлу браузера")
        p.add_argument("--headless", action="store_true", help="без окна браузера (сайты чаще блокируют)")

    c = sub.add_parser("collect", help="собрать цены")
    c.add_argument("--stores", help="сети через запятую, например magnit,lenta (по умолчанию все)")
    c.add_argument("--products", help="id продуктов через запятую (по умолчанию все)")
    c.add_argument("--limit", type=int, help="взять только первые N продуктов (для проверки)")
    c.add_argument("--api-only", action="store_true", help="только API Магнита, без браузера")
    c.add_argument("--delay", type=float, default=2.0, help="пауза между запросами в одной сети, сек")
    c.add_argument("--out", default=str(PRICES_PATH))
    browser_opts(c)

    s = sub.add_parser("setup", help="выбрать адрес/магазин на сайтах сетей")
    s.add_argument("--stores")
    browser_opts(s)

    d = sub.add_parser("diagnose", help="проверить одну сеть на одном запросе")
    d.add_argument("store")
    d.add_argument("query")
    browser_opts(d)

    v = sub.add_parser("serve", help="открыть приложение в локальной сети")
    v.add_argument("--port", type=int, default=8080)

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.cmd == "serve":
        return cmd_serve(args)
    fn = {"collect": cmd_collect, "setup": cmd_setup, "diagnose": cmd_diagnose}[args.cmd]
    return asyncio.run(fn(args))


if __name__ == "__main__":
    sys.exit(main())
