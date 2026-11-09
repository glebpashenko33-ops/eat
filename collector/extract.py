"""Универсальный поиск товаров в JSON-ответах сайтов магазинов.

Сайты сетей устроены по-разному, но в ответах их собственных API товар — это объект
с названием и ценой. Обходим JSON и собираем такие объекты, не завязываясь на формат
конкретной сети: так сборщик переживает смену API без правок кода."""

from __future__ import annotations

import json
import re
from typing import Any, Iterator

NAME_KEYS = ("name", "title", "productName", "product_name", "displayName", "fullName", "full_name", "shortName")
URL_KEYS = ("url", "link", "href", "slug", "canonicalUrl")
_CYR = re.compile(r"[а-яё]", re.I)
_PRICE_CONTEXT = re.compile(r"pric|cost|цена", re.I)
_SKIP_KEY = re.compile(
    r"old|before|crossed|strike|percent|economy|saving|diff|delta|bonus|point|cashback|max|min_?order|"
    r"rating|(?<!dis)count|quantity|stock|limit|step|weight|volume|id$|code|vat|tax|deposit|delivery",
    re.I,
)
_UNIT_PRICE_KEY = re.compile(r"unit_?price|per_?kg|per_?unit|by_?kg|price_?per|kg_?price", re.I)
_WEIGHT_KEY = re.compile(r"^(weight|netto|net_?weight|package_?weight)$", re.I)


def _name_of(obj: dict) -> str | None:
    for k in NAME_KEYS:
        v = obj.get(k)
        if isinstance(v, str) and 3 <= len(v) <= 250 and _CYR.search(v):
            return v.strip()
    return None


def _numbers(obj: Any, path: str, depth: int, out: list[tuple[str, float]]) -> None:
    if depth > 3:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _numbers(v, f"{path}.{k}" if path else str(k), depth + 1, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        out.append((path, float(obj)))
    elif isinstance(obj, str):
        s = obj.replace(" ", "").replace(" ", "").replace(",", ".")
        if re.fullmatch(r"\d+(\.\d{1,2})?", s) and _PRICE_CONTEXT.search(path):
            out.append((path, float(s)))


def product_from_dict(obj: dict) -> dict | None:
    name = _name_of(obj)
    if not name:
        return None
    prices: list[float] = []
    unit_price = None
    weight_kg = None
    for k, v in obj.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and _WEIGHT_KEY.match(k):
            if v > 0:
                weight_kg = v / 1000 if v >= 10 else float(v)
            continue
        is_unit = bool(_UNIT_PRICE_KEY.search(k))
        if isinstance(v, dict) and not is_unit and not _PRICE_CONTEXT.search(k):
            # цена за кг бывает вложена в объект без «price» в имени: {"weighted": {"unitPrice": ...}}
            for kk, vv in v.items():
                if _UNIT_PRICE_KEY.search(kk) and isinstance(vv, (int, float)) and not isinstance(vv, bool) and vv > 0:
                    unit_price = vv if unit_price is None else min(unit_price, vv)
            continue
        if not is_unit and (not _PRICE_CONTEXT.search(k) or _SKIP_KEY.search(k)):
            continue
        nums: list[tuple[str, float]] = []
        _numbers(v, k, 1, nums)
        for path, val in nums:
            if val <= 0 or val > 10_000_000:
                continue
            segs = path.split(".")
            if any(_SKIP_KEY.search(s) for s in segs[1:]):
                continue
            if is_unit or any(_UNIT_PRICE_KEY.search(s) for s in segs[1:]):
                unit_price = val if unit_price is None else min(unit_price, val)
            else:
                prices.append(val)
    if not prices and unit_price is None:
        return None
    url = None
    for k in URL_KEYS:
        v = obj.get(k)
        if isinstance(v, str) and len(v) < 300:
            url = v
            break
    out = {"name": name, "prices": sorted(set(prices)) or [unit_price]}
    if unit_price is not None:
        out["unit_price"] = unit_price
    if weight_kg:
        out["weight_kg"] = weight_kg
    if url:
        out["url"] = url
    return out


def walk(obj: Any, depth: int = 0) -> Iterator[dict]:
    if depth > 40:
        return
    if isinstance(obj, dict):
        p = product_from_dict(obj)
        if p:
            yield p
        for v in obj.values():
            if isinstance(v, (dict, list)):
                yield from walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, (dict, list)):
                yield from walk(v, depth + 1)


def candidates_from_json(data: Any) -> list[dict]:
    seen: set[tuple] = set()
    out = []
    for c in walk(data):
        key = (c["name"], tuple(c["prices"]))
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


_SCRIPT_JSON = re.compile(
    r'<script[^>]*(?:id="__NEXT_DATA__"|type="application/(?:ld\+)?json")[^>]*>(.*?)</script>', re.S | re.I
)


def candidates_from_html(html: str) -> list[dict]:
    """Данные, встроенные в страницу: __NEXT_DATA__, JSON-LD и другие JSON-скрипты."""
    out: list[dict] = []
    for m in _SCRIPT_JSON.finditer(html):
        try:
            data = json.loads(m.group(1))
        except (ValueError, RecursionError):
            continue
        out.extend(candidates_from_json(data))
        out.extend(_from_ld(data))
    return out


def _from_ld(data: Any) -> list[dict]:
    """schema.org Product: {"@type": "Product", "name", "offers": {"price"}}."""
    out = []
    items = data if isinstance(data, list) else [data]
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("@type") == "ItemList":
            out.extend(_from_ld([e.get("item", e) for e in it.get("itemListElement", []) if isinstance(e, dict)]))
        if it.get("@type") == "Product" and isinstance(it.get("name"), str):
            offers = it.get("offers")
            offers = offers if isinstance(offers, list) else [offers]
            prices = []
            for o in offers:
                if isinstance(o, dict) and o.get("@type") != "AggregateOffer":  # сводка по всей выдаче, не товар
                    for k in ("price", "lowPrice"):
                        try:
                            prices.append(float(str(o.get(k)).replace(",", ".")))
                        except ValueError:
                            pass
            if prices:
                out.append({"name": it["name"], "prices": sorted(set(p for p in prices if p > 0)), "url": it.get("url")})
    return out
