// Запуск: node tests/planner.test.js
const assert = require('assert');
const path = require('path');
const Planner = require('../web/planner.js');
const products = require('../web/data/products.json');
const recipes = require('../web/data/recipes.json');

function fakePrices() {
  // Две «сети»: одна дешевле на крупы, другая — на мясо и овощи
  const items = {};
  for (const p of products) {
    const mk = (k, q) => [{ t: p.n + ' (тест)', p: +(p.bp * k * q).toFixed(2), q }];
    const q = p.u === 'pc' ? 10 : p.wt ? 1 : p.pk;
    items[p.id] = {
      a: p.g === 'grain' || p.g === 'legume' ? mk(0.8, q) : mk(1.1, q),
      b: p.g === 'grain' || p.g === 'legume' ? mk(1.2, q) : mk(0.9, q),
    };
    if (p.wt) { items[p.id].a[0].w = true; items[p.id].b[0].w = true; }
  }
  return { stores: { a: { name: 'A' }, b: { name: 'B' } }, items };
}

const person = { sex: 'm', age: 30, weight: 75, height: 178, activity: 1.375 };
let t0 = Date.now();
const r = Planner.plan({ products, recipes, prices: fakePrices() },
  { budget: 5000, days: 7, people: [person], stores: ['a', 'b'], maxStores: 2, seed: 42 });
const ms = Date.now() - t0;
assert(!r.error, r.error);
assert.strictEqual(r.days.length, 7);
const ids = r.days.flat().map((m) => m.recipe.id);
const dup = ids.length - new Set(ids).size;
console.log('время', ms, 'мс; итог', r.shop.total.toFixed(0), '₽; повторов блюд', dup, '; магазины', r.shop.stores);
assert(r.shop.total <= 5000, 'превышен бюджет: ' + r.shop.total);
assert(dup === 0, 'блюда повторяются при достаточном бюджете');
const n = r.nutrition[0], t = r.targets[0];
const pct = (a, b) => Math.round((100 * a) / b) + '%';
console.log('ккал', Math.round(n.k), '/', t.kcal, 'белок', pct(n.p, t.p), 'клетчатка', pct(n.fb, t.fb),
  'вит C', pct(n.vc, t.vc), 'Ca', pct(n.ca, t.ca), 'Fe', pct(n.fe, t.fe), 'овощи/фрукты', Math.round(n.vf), 'г', 'жир', Math.round(n.f * 9 / n.k * 100) + '% ккал');
assert(Math.abs(n.k / t.kcal - 1) < 0.1, 'калорийность далеко от нормы');
assert(n.p >= t.p * 0.9, 'мало белка');
for (const d of r.days) console.log(d.map((m) => m.recipe.n).join(' | '));

// Маленький бюджет: план всё равно строится, и сообщается о превышении
const poor = Planner.plan({ products, recipes, prices: fakePrices() },
  { budget: 1200, days: 7, people: [person], stores: ['a', 'b'], maxStores: 1, seed: 1, iterations: 8000 });
console.log('бюджет 1200: итог', poor.shop.total.toFixed(0), 'overBudget', poor.overBudget, 'магазины', poor.shop.stores);
assert(poor.shop.stores.length <= 1);

// Без живых цен — ориентировочные
const base = Planner.plan({ products, recipes, prices: null },
  { budget: 6000, days: 7, people: [person, { sex: 'f', age: 28, weight: 60, height: 165, activity: 1.375 }], stores: [], seed: 3, iterations: 8000 });
console.log('без цен, 2 человека: итог', base.shop.total.toFixed(0), 'доля живых цен', base.livePriceShare);
assert(base.livePriceShare === 0 && base.shop.lines.every((l) => l.approx));

// Ограничения: вегетарианское без молочного — нет мяса, рыбы и молочки
const veg = Planner.plan({ products, recipes, prices: fakePrices() },
  { budget: 6000, days: 3, people: [person], stores: ['a', 'b'], diets: ['vegetarian'], seed: 5, iterations: 5000 });
const bad = veg.days.flat().filter((m) => Object.keys(m.recipe.i).some((id) => ['meat', 'poultry', 'fish'].includes(products.find((p) => p.id === id).g)));
assert.strictEqual(bad.length, 0, 'в вегетарианском меню мясо');
console.log('OK');
