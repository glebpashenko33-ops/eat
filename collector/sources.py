"""Источники цен: прямой API Магнита и универсальный сбор через браузер."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from .catalog import Offer, pick_offers
from .extract import candidates_from_html, candidates_from_json

log = logging.getLogger("collector")
CONFIG_PATH = Path(__file__).resolve().parent / "stores.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


# ── Магнит: прямой API (работает без браузера, в том числе в GitHub Actions) ──

def magnit_api_search(cfg: dict, query: str, timeout: float = 20) -> list[dict]:
    body = json.dumps({
        "term": query,
        "pagination": {"limit": 36, "offset": 0},
        "sort": {"order": "asc", "type": "price"},
        "storeCode": cfg["storeCode"],
        "storeType": "1",
        "catalogType": "1",
    }).encode("utf-8")
    req = urllib.request.Request(cfg["url"], data=body, method="POST", headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://magnit.ru",
        "Referer": "https://magnit.ru/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return candidates_from_json(json.loads(r.read().decode("utf-8")))


def collect_magnit_api(products: list[dict], cfg: dict, delay: float = 0.4) -> dict[str, list[Offer]]:
    out: dict[str, list[Offer]] = {}
    errors = 0
    for prod in products:
        try:
            offers = pick_offers(prod, magnit_api_search(cfg, prod["q"]))
        except Exception as e:  # noqa: BLE001 — сеть, формат: товар пропускаем, остальное собираем
            errors += 1
            log.warning("Магнит API: %s — %s: %s", prod["n"], type(e).__name__, e)
            if errors >= 5 and not out:
                log.error("Магнит API не отвечает, прекращаю")
                break
            continue
        if offers:
            out[prod["id"]] = offers
        log.info("Магнит API: %-28s %s", prod["n"], _fmt(offers, prod))
        _sleep(delay)
    return out


def _sleep(sec: float) -> None:
    import time
    time.sleep(sec * random.uniform(0.7, 1.4))


def _fmt(offers: list[Offer], prod: dict) -> str:
    if not offers:
        return "— не найдено"
    o = offers[0]
    unit = {"kg": "кг", "l": "л", "pc": "шт"}[prod["u"]]
    return f"{o.per_unit:8.2f} ₽/{unit}  {o.title[:60]}"


# ── Универсальный сбор через браузер ──

SEARCH_INPUTS = [
    "input[type=search]",
    "input[name*=search i]",
    "input[name=q]",
    "input[placeholder*='оиск']",
    "input[placeholder*='айти']",
    "input[placeholder*='earch']",
]


# Выполняется на странице: состояние JS-фреймворка (Nuxt/Next/Redux) и карточки товаров с ценой в ₽.
PAGE_JS = r"""() => {
  const state = [];
  for (const k of ['__NUXT__', '__NEXT_DATA__', '__INITIAL_STATE__', '__PRELOADED_STATE__', '__APOLLO_STATE__', '__STATE__', '__DATA__']) {
    try { if (window[k]) state.push(JSON.parse(JSON.stringify(window[k]))); } catch (e) {}
  }
  const priceRe = /^\s*(\d[\d\s\u00a0\u202f]*(?:[.,]\d{1,2})?)\s*₽\s*$/;
  const num = (s) => parseFloat(s.replace(/[\s\u00a0\u202f]/g, '').replace(',', '.'));
  const cards = new Map();
  const qtyRe = /\d+(?:[.,]\d+)?\s*(?:кг|гр|г|мл|л|шт)(?![а-яёa-z])/i;
  const matches = [];
  for (const el of document.querySelectorAll('body *')) {
    const t = (el.innerText || '').trim();
    if (t.length < 25 && priceRe.test(t)) matches.push(el);
  }
  // берём самые глубокие элементы с ценой: «109,99 ₽» может быть разбит на несколько <span>
  const leaves = matches.filter((el) => ![...el.children].some((c) => priceRe.test((c.innerText || '').trim())));
  for (const leaf of leaves.slice(0, 600)) {
    let card = leaf;
    for (let i = 0; i < 14 && card.parentElement; i++) {
      card = card.parentElement;
      const txt = card.innerText || '';
      if (txt.length > 900) break;
      const lines = txt.split('\n').map((x) => x.trim()).filter(Boolean);
      const titles = lines.filter((x) => /[а-яё]{3,}/i.test(x) && !/₽/.test(x) && x.length >= 8 && !/^(цена за|с картой|до \d|в корзину|купить)/i.test(x));
      if (titles.length) {
        if (!cards.has(card)) {
          let name = titles.sort((a, b) => b.length - a.length)[0];
          const qty = lines.find((x) => qtyRe.test(x) && x.length < 20 && !/₽/.test(x));
          if (!qtyRe.test(name) && qty) name += ' ' + qty;
          cards.set(card, { name, prices: [] });
        }
        cards.get(card).prices.push(num(leaf.innerText.trim().match(priceRe)[1]));
        break;
      }
    }
  }
  return { state, dom: [...cards.values()].filter((c) => c.prices.every((p) => p > 0)) };
}"""


class BrowserStore:
    """Открывает поиск сети в браузере и собирает товары из JSON-ответов сайта и из самой страницы."""

    def __init__(self, store_id: str, store: dict, page, wait_ms: int = 3500):
        self.id = store_id
        self.store = store
        self.page = page
        self.wait_ms = wait_ms
        self._bucket: list[dict] | None = None
        self._pending: set = set()
        page.on("response", self._on_response)

    def _on_response(self, resp) -> None:
        if self._bucket is None:
            return
        ctype = (resp.headers or {}).get("content-type", "")
        if "json" not in ctype:
            return
        task = asyncio.ensure_future(self._read(resp))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _read(self, resp) -> None:
        try:
            data = await resp.json()
        except Exception:  # noqa: BLE001 — тело недоступно или не JSON
            return
        if self._bucket is not None:
            self._bucket.extend(candidates_from_json(data))

    async def _settle(self) -> None:
        try:
            await self.page.wait_for_load_state("networkidle", timeout=self.wait_ms * 3)
        except Exception:  # noqa: BLE001 — сайты с постоянными запросами не затихают, это нормально
            pass
        await self.page.wait_for_timeout(self.wait_ms)
        if self._pending:
            await asyncio.wait(list(self._pending), timeout=5)

    async def search(self, query: str) -> list[dict]:
        self._bucket = []
        url = self.store["search"].replace("{q}", urllib.parse.quote(query))
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await self._settle()
            await self._scan_page()
            if not self._bucket:
                await self._search_via_input(query)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: ошибка поиска «%s»: %s", self.store["name"], query, e)
        found, self._bucket = self._bucket, None
        return found

    async def _scan_page(self) -> None:
        """Товары, уже встроенные в страницу: JSON в HTML, состояние фреймворка и карточки в разметке."""
        self._bucket.extend(candidates_from_html(await self.page.content()))
        try:
            got = await self.page.evaluate(PAGE_JS)
        except Exception as e:  # noqa: BLE001
            log.debug("%s: разбор страницы не удался: %s", self.store["name"], e)
            return
        for st in got.get("state", []):
            self._bucket.extend(candidates_from_json(st))
        # карточки из разметки берём всегда: лишнее отсеет сопоставление по названию и цене
        self._bucket.extend(c for c in got.get("dom", []) if c.get("name") and c.get("prices"))

    async def _search_via_input(self, query: str) -> None:
        """Запасной путь: ввести запрос в строку поиска на главной."""
        await self.page.goto(self.store["home"], wait_until="domcontentloaded", timeout=45000)
        await self._settle()
        for sel in SEARCH_INPUTS:
            loc = self.page.locator(sel).first
            try:
                if await loc.count() and await loc.is_visible():
                    # поле часто закрыто «заглушкой» — кликаем принудительно и печатаем в то, что получило фокус
                    await loc.click(timeout=3000, force=True)
                    await self.page.wait_for_timeout(800)
                    await self.page.keyboard.press("Control+A")
                    await self.page.keyboard.type(query, delay=40)
                    await self.page.wait_for_timeout(800)
                    await self.page.keyboard.press("Enter")
                    await self._settle()
                    await self._scan_page()
                    return
            except Exception:  # noqa: BLE001
                continue


async def collect_browser_store(store_id: str, store: dict, context, products: list[dict],
                                delay: float, progress: Callable[[str], None] | None = None) -> dict[str, list[Offer]]:
    page = await context.new_page()
    bs = BrowserStore(store_id, store, page)
    out: dict[str, list[Offer]] = {}
    misses = 0
    for i, prod in enumerate(products):
        cands = await bs.search(prod["q"])
        offers = pick_offers(prod, cands)
        if offers:
            out[prod["id"]] = offers
            misses = 0
        else:
            misses += 1
        log.info("%s [%d/%d]: %-28s %s (кандидатов %d)", store["name"], i + 1, len(products), prod["n"],
                 _fmt(offers, prod), len(cands))
        if progress:
            progress(store_id)
        if misses >= 8 and not out:
            log.error("%s: 8 запросов подряд без товаров — сайт не отдаёт цены (блокировка, капча или смена поиска). "
                      "Запустите «python -m collector setup» и проверьте сайт вручную.", store["name"])
            break
        await asyncio.sleep(delay * random.uniform(0.6, 1.5))
    await page.close()
    return out
