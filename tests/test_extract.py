"""Разбор ответов разных форматов и выбор товаров. Запуск: python -m pytest tests"""

from collector.catalog import load_products, parse_quantity, pick_offers
from collector.extract import candidates_from_html, candidates_from_json

P = {p["id"]: p for p in load_products()}


def test_parse_quantity():
    assert parse_quantity("Молоко Простоквашино 2,5% 930 мл", "l") == (0.93, False)
    assert parse_quantity("Гречка ядрица 900г", "kg") == (0.9, False)
    assert parse_quantity("Йогурт 2 x 150 г", "kg") == (0.3, False)
    assert parse_quantity("Картофель весовой", "kg") == (1.0, True)
    assert parse_quantity("Яйцо куриное С1 10шт", "pc") == (10.0, False)
    assert parse_quantity("Огурцы гладкие, 1 кг", "kg")[0] == 1.0
    assert parse_quantity("Рис", "kg") == (None, False)


def test_magnit_like_kopecks_and_weighted():
    data = {"items": [
        {"id": 1, "name": "Молоко Домик в деревне 2,5% 900 мл", "price": 8999, "promotion": {"oldPrice": 10999}},
        {"id": 2, "name": "Молоко сгущённое 380 г", "price": 9999},
        {"id": 3, "name": "Картофель весовой", "price": 4999, "weighted": {"unitPrice": 4999}},
    ]}
    cands = candidates_from_json(data)
    milk = pick_offers(P["milk"], cands)
    assert len(milk) == 1 and abs(milk[0].price - 89.99) < 0.01 and milk[0].q == 0.9
    potato = pick_offers(P["potato"], cands)
    assert potato and potato[0].weighted and abs(potato[0].price - 49.99) < 0.01


def test_x5_like_string_prices_takes_promo():
    data = {"products": [{"plu": 5, "name": "Кефир Простоквашино 1% 930 г",
                          "prices": {"regular": "109.99", "discount": "84.99"}, "rating": {"rating_average": 4.8}}]}
    offers = pick_offers(P["kefir"], candidates_from_json(data))
    assert offers and abs(offers[0].price - 84.99) < 0.01


def test_nested_price_tag_and_skip_old():
    data = {"content": {"items": [{"title": "Гречка Мистраль ядрица 900 г",
                                   "priceTag": {"price": 8990, "grossPrice": 11990},
                                   "oldPrice": 1, "discountPercent": 25}]}}
    offers = pick_offers(P["buckwheat"], candidates_from_json(data))
    assert offers and abs(offers[0].price - 89.90) < 0.01


def test_html_next_data_and_ld_json():
    html = """<html><script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"goods":[{"name":"Рис круглозерный Акмаль 800 г","price":{"value":95.5}}]}}}
    </script><script type="application/ld+json">
    {"@type":"ItemList","itemListElement":[{"item":{"@type":"Product","name":"Чечевица красная 450 г","offers":{"price":"119.90"}}}]}
    </script></html>"""
    cands = candidates_from_html(html)
    assert pick_offers(P["rice"], cands)[0].price == 95.5
    assert abs(pick_offers(P["lentils"], cands)[0].price - 119.9) < 0.01


def test_rejects_implausible_price_and_mismatch():
    data = [{"name": "Сыр плавленый 90 г", "price": 59.9},
            {"name": "Сыр Российский 200 г", "price": 9.0},  # слишком дёшево — ошибка разбора
            {"name": "Сыр Российский 200 г", "price": 169.9}]
    offers = pick_offers(P["cheese"], candidates_from_json(data))
    assert [round(o.price, 1) for o in offers] == [169.9]


def test_eggs_per_piece():
    data = [{"name": "Яйцо куриное С1 10 шт", "price": 119.99}, {"name": "Яйцо перепелиное 20 шт", "price": 150}]
    offers = pick_offers(P["eggs"], candidates_from_json(data))
    assert len(offers) == 1 and offers[0].q == 10 and abs(offers[0].per_unit - 12.0) < 0.01


def test_keyword_must_name_the_product_itself():
    data = [{"name": "Хлопья овсяные с черносливом 300 г", "price": 105},
            {"name": "Йогурт с кленовым сиропом и грецким орехом 150 г", "price": 60},
            {"name": "Чернослив без косточки 200 г", "price": 120},
            {"name": "Фасоль красная в собственном соку 400 г", "price": 99}]
    cands = candidates_from_json(data)
    assert [o.title for o in pick_offers(P["prunes"], cands)] == ["Чернослив без косточки 200 г"]
    assert pick_offers(P["walnuts"], cands) == []
    assert pick_offers(P["beans_canned"], cands)


def test_rejects_non_food_and_flavoured_goods():
    data = [{"name": "Свеча HOMECLUB Мандарин большой", "price": 99.99},
            {"name": "Удобрение для открытого грунта Кабачки 1 кг", "price": 111},
            {"name": "Йогурт питьевой Персик, груша 1,5% 900 г", "price": 113},
            {"name": "Груши Вильямс весовые", "price": 189.9},
            {"name": "Капуста брокколи замороженная 400 г", "price": 129}]
    cands = candidates_from_json(data)
    assert pick_offers(P["mandarin"], cands) == []
    assert pick_offers(P["zucchini"], cands) == []
    assert [o.title for o in pick_offers(P["pear"], cands)] == ["Груши Вильямс весовые"]
    assert pick_offers(P["broccoli"], cands)
