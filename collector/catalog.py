"""Каталог продуктов, разбор фасовки из названия и выбор подходящих товаров."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_PATH = ROOT / "web" / "data" / "products.json"

# Цена за единицу, отличающаяся от ориентира сильнее этого, считается ошибкой сопоставления.
RATIO_MIN, RATIO_MAX = 0.3, 3.0


def load_products(path: Path = PRODUCTS_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()


_NUM = r"(\d+(?:[.,]\d+)?)"
_MULTI = re.compile(_NUM + r"\s*(?:шт\.?\s*)?[xх×*]\s*" + _NUM + r"\s*(кг|г|гр|л|мл)\b")
_SINGLE = re.compile(_NUM + r"\s*(кг|г|гр|л|мл)\b")
_PCS = re.compile(r"(\d+)\s*(?:шт|штук)\b")
_PER_KG = re.compile(r"(?:\bза\s*1?\s*кг\b|/\s*кг\b|\bвесов|\bна вес\b|\b1\s*кг\b)")


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def parse_quantity(name: str, unit: str) -> tuple[float | None, bool]:
    """Количество в единицах продукта (кг / л / шт) из названия товара.

    Возвращает (количество, весовой_товар). Для весовых товаров количество = 1 (цена за кг)."""
    n = norm(name)
    if unit == "pc":
        m = _PCS.search(n)
        if m:
            return float(m.group(1)), False
        if "десяток" in n:
            return 10.0, False
        return None, False
    m = _MULTI.search(n)
    if m:
        count, val, u = _f(m.group(1)), _f(m.group(2)), m.group(3)
        if count > 50:  # «150 г x 2» записано наоборот
            count, val = val, count
        return count * _to_base(val, u), False
    found = list(_SINGLE.finditer(n))
    if found:
        m = found[-1]
        q = _to_base(_f(m.group(1)), m.group(2))
        if q > 0:
            return q, bool(_PER_KG.search(n)) and q == 1.0
    if _PER_KG.search(n):
        return 1.0, True
    return None, False


def _to_base(val: float, u: str) -> float:
    return val / 1000 if u in ("г", "гр", "мл") else val


@dataclass
class Offer:
    title: str
    price: float  # рублей за q
    q: float  # количество в единицах продукта
    weighted: bool = False
    url: str | None = None

    @property
    def per_unit(self) -> float:
        return self.price / self.q

    def to_json(self) -> dict:
        d = {"t": self.title[:120], "p": round(self.price, 2), "q": round(self.q, 4)}
        if self.weighted:
            d["w"] = True
        if self.url:
            d["url"] = self.url
        return d


_CONNECTOR = re.compile(r"\s(?:с|со|в|во|из|и|для|под|на|без)\s")


# Непищевые и переработанные товары, которые поиск сетей подмешивает в выдачу
GLOBAL_EXCLUDE = ("удобрен", "свеча", "ароматизатор", "освежител", "шампун", "мыло", "гель ", "корм ", "для кошек",
                  "для собак", "наггетс", "кетчуп", "сухари", "нектар", "напиток", "лосьон", "игрушк", "грунт",
                  "детск", "пюре фрукт", "чипсы", "батончик", "мармелад", "конфет")
# Для простых продуктов ключевое слово должно быть в первых словах: «Груши Вильямс», а не «Йогурт персик, груша»
HEAD_WORDS = {"veg": 2, "fruit": 2, "meat": 2, "poultry": 2, "fish": 2, "egg": 2, "dairy": 2, "fat": 2}


def name_matches(product: dict, title: str) -> bool:
    """Ключевое слово должно описывать сам товар: стоять в начале и до «с», «в», «из»…
    («Йогурт с грецким орехом» — не орех, «Свеча Мандарин» — не мандарин)."""
    t = norm(title)
    if any(g in t + " " for g in GLOBAL_EXCLUDE):
        return False
    head_end = m.start() if (m := _CONNECTOR.search(" " + t + " ")) else len(t)
    head = " ".join(t[: max(head_end, 0)].split()[: HEAD_WORDS.get(product["g"], 5)])
    if not any(norm(k) in head for k in product["m"]):
        return False
    return not any(norm(x) in t for x in product["x"])


def offer_from_candidate(product: dict, cand: dict) -> Offer | None:
    """Кандидат из extract.py -> предложение в единицах продукта или None, если не подходит."""
    title = cand["name"]
    if not name_matches(product, title):
        return None
    base = product["bp"]
    q, weighted = parse_quantity(title, product["u"])
    unit_price = cand.get("unit_price")
    if q is None:
        if cand.get("weight_kg") and product["u"] != "pc":
            q = cand["weight_kg"]
        elif product.get("wt") or unit_price:
            q, weighted = 1.0, True
        elif product["u"] == "pc":
            q = 10.0
        else:
            return None
    raws = [unit_price] if weighted and unit_price else cand["prices"]
    best: Offer | None = None
    for raw in raws:
        # Цена может быть в рублях или в копейках: берём масштаб, ближайший к ориентиру.
        options = [raw, raw / 100] if float(raw).is_integer() else [raw]
        price = min(options, key=lambda p: abs(math.log(p / q / base)))
        if not (RATIO_MIN <= price / q / base <= RATIO_MAX):
            continue
        off = Offer(title, price, q, weighted, cand.get("url"))
        if best is None or off.per_unit < best.per_unit:  # самая низкая — текущая/акционная
            best = off
    return best


def pick_offers(product: dict, candidates: list[dict], limit: int = 3) -> list[Offer]:
    """Лучшие предложения: самые дешёвые за кг/л/шт, с разной фасовкой."""
    offers = [o for c in candidates if (o := offer_from_candidate(product, c))]
    offers.sort(key=lambda o: o.per_unit)
    out: list[Offer] = []
    seen_q: set[float] = set()
    for o in offers:
        key = round(o.q, 3)
        if key in seen_q:
            continue
        seen_q.add(key)
        out.append(o)
        if len(out) >= limit:
            break
    return out
