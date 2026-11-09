/* Подбор рациона под бюджет: меню на N дней по рецептам + список покупок по магазинам.
   Работает и в браузере (window.Planner), и в Node (module.exports) — для тестов. */
(function (root) {
  'use strict';

  const SLOTS = ['b', 'l', 'd', 'k'];
  const SLOT_NAMES = { b: 'Завтрак', l: 'Обед', d: 'Ужин', k: 'Перекус' };
  const SLOT_SHARE = { b: 0.25, l: 0.35, d: 0.28, k: 0.12 };
  const SLOT_TYPES = { b: ['b'], l: ['s', 'm'], d: ['m'], k: ['k'] };
  const NUTS = ['k', 'p', 'f', 'c', 'fb', 'vc', 'ca', 'fe'];
  const PORTION = { lo: 0.6, hi: 1.8, soupHi: 2.2 };

  const DIETS = {
    no_fish: { name: 'Без рыбы', groups: ['fish'] },
    no_pork: { name: 'Без свинины', ids: ['pork', 'minced_meat'] },
    no_beef: { name: 'Без говядины', ids: ['beef', 'minced_meat'] },
    vegetarian: { name: 'Вегетарианское', groups: ['meat', 'poultry', 'fish'] },
    no_dairy: { name: 'Без молочного', groups: ['dairy'], ids: ['butter'] },
    no_eggs: { name: 'Без яиц', groups: ['egg'] },
    no_liver: { name: 'Без субпродуктов', ids: ['chicken_liver'] },
  };

  // ── Нормы на человека в день ──
  function personTargets(p) {
    const w = +p.weight || 70, h = +p.height || 170, a = +p.age || 30;
    const male = p.sex !== 'f';
    let kcal;
    if (a < 14) kcal = 1000 + 100 * a;
    else kcal = (10 * w + 6.25 * h - 5 * a + (male ? 5 : -161)) * (+p.activity || 1.375);
    if (p.goal === 'lose') kcal *= 0.85;
    if (p.goal === 'gain') kcal *= 1.1;
    kcal = Math.round(kcal / 10) * 10;
    const kidK = Math.min(1, kcal / 2000);
    return {
      kcal,
      p: Math.max(a < 14 ? 1.1 * w : 1.0 * w, (0.15 * kcal) / 4),
      fatMin: (0.2 * kcal) / 9,
      fatMax: (0.35 * kcal) / 9,
      fb: (14 * kcal) / 1000,
      vc: a < 14 ? 60 : 90,
      ca: a >= 11 && a < 19 ? 1200 : 1000,
      fe: !male && a >= 14 && a < 50 ? 18 : 10,
      vf: a < 14 ? 300 : 400 * Math.max(0.8, kidK),
    };
  }

  // ── Справочники ──
  function indexProducts(products) {
    const map = {};
    for (const p of products) map[p.id] = p;
    return map;
  }

  // грамм съедобной части -> единиц покупки (кг, л или шт), с учётом отходов
  function gramsToUnits(prod, grams) {
    const raw = grams / (prod.y || 1);
    if (prod.u === 'pc') return raw / (prod.pcg || 55);
    if (prod.u === 'l') return raw / 1000 / (prod.d || 1);
    return raw / 1000;
  }

  function recipeNutrition(recipe, P) {
    const n = { k: 0, p: 0, f: 0, c: 0, fb: 0, vc: 0, ca: 0, fe: 0, vf: 0 };
    for (const [id, g] of Object.entries(recipe.i)) {
      const pr = P[id];
      if (!pr) continue;
      for (const key of NUTS) n[key] += (pr[key] || 0) * g / 100;
      if ((pr.g === 'veg' || pr.g === 'fruit') && id !== 'potato' && id !== 'tomato_paste') {
        n.vf += (id === 'raisins' || id === 'prunes') ? g * 2.5 : g;
      }
    }
    return n;
  }

  function recipeAllowed(recipe, P, opts) {
    const banIds = new Set(opts.dislikes || []);
    const banGroups = new Set();
    for (const d of opts.diets || []) {
      const def = DIETS[d];
      if (!def) continue;
      (def.ids || []).forEach((x) => banIds.add(x));
      (def.groups || []).forEach((x) => banGroups.add(x));
    }
    for (const id of Object.keys(recipe.i)) {
      if (banIds.has(id)) return false;
      const pr = P[id];
      if (pr && banGroups.has(pr.g)) return false;
    }
    return true;
  }

  // ── Цены ──
  // prices.json: { stores: {id: {name, updated}}, items: {productId: {storeId: [{t, p, q, w}]}} }
  // q — количество в единицах товара (кг/л/шт) за цену p; w — весовой товар (цена p за 1 единицу).
  function buildPriceIndex(products, prices, storeIds) {
    const allowed = new Set(storeIds || []);
    const idx = {};
    for (const prod of products) {
      const perStore = {};
      const items = (prices && prices.items && prices.items[prod.id]) || {};
      for (const [sid, list] of Object.entries(items)) {
        if (!allowed.has(sid) || !Array.isArray(list)) continue;
        const ok = list.filter((it) => it && it.p > 0 && it.q > 0);
        if (ok.length) perStore[sid] = ok;
      }
      let minUnit = Infinity;
      for (const list of Object.values(perStore)) for (const it of list) minUnit = Math.min(minUnit, it.p / it.q);
      const live = minUnit < Infinity;
      idx[prod.id] = { perStore, live, unit: live ? minUnit : prod.bp };
    }
    return idx;
  }

  // ── Оценка плана ──
  function makeContext(data, opts) {
    const P = indexProducts(data.products);
    const people = (opts.people && opts.people.length ? opts.people : [{}]).map(personTargets);
    const recipes = data.recipes.filter((r) => recipeAllowed(r, P, opts)).map((r) => {
      const nut = recipeNutrition(r, P);
      return Object.assign({}, r, { nut });
    });
    const pantry = new Set(opts.pantry || []);
    const priceIdx = buildPriceIndex(data.products, data.prices, opts.stores);
    // стоимость одного грамма каждого продукта по лучшей цене
    const gramCost = {};
    for (const prod of data.products) {
      gramCost[prod.id] = pantry.has(prod.id) ? 0 : gramsToUnits(prod, 1) * priceIdx[prod.id].unit;
    }
    for (const r of recipes) {
      r.cost = 0;
      for (const [id, g] of Object.entries(r.i)) r.cost += (gramCost[id] || 0) * g;
    }
    const pools = {};
    for (const s of SLOTS) pools[s] = recipes.map((r, i) => (SLOT_TYPES[s].includes(r.t) ? i : -1)).filter((i) => i >= 0);
    return {
      P, people, recipes, pools, pantry, priceIdx, gramCost,
      days: Math.max(1, Math.min(14, +opts.days || 7)),
      history: new Set(opts.history || []),
      products: data.products,
    };
  }

  function portion(ctx, recipe, slot, person) {
    const hi = recipe.t === 's' ? PORTION.soupHi : PORTION.hi;
    const m = (person.kcal * SLOT_SHARE[slot]) / Math.max(1, recipe.nut.k);
    return Math.min(hi, Math.max(PORTION.lo, m));
  }

  function evaluate(ctx, plan, budget) {
    const { people, recipes, days } = ctx;
    let pen = 0, cost = 0;
    const per = people.map(() => ({ p: 0, f: 0, fb: 0, vc: 0, ca: 0, fe: 0, vf: 0 }));
    const used = new Map();
    let fish = 0;
    for (let d = 0; d < days; d++) {
      const day = plan[d];
      const dayK = people.map(() => 0);
      for (let si = 0; si < 4; si++) {
        const slot = SLOTS[si];
        const r = recipes[day[si]];
        used.set(r.id, (used.get(r.id) || 0) + 1);
        if (r.pr === 'fish' && slot !== 'b' && slot !== 'k') fish++;
        let mult = 0;
        for (let pi = 0; pi < people.length; pi++) {
          const m = portion(ctx, r, slot, people[pi]);
          mult += m;
          dayK[pi] += r.nut.k * m;
          const a = per[pi];
          a.p += r.nut.p * m; a.f += r.nut.f * m; a.fb += r.nut.fb * m;
          a.vc += r.nut.vc * m; a.ca += r.nut.ca * m; a.fe += r.nut.fe * m; a.vf += r.nut.vf * m;
        }
        cost += r.cost * mult;
        if (ctx.history.has(r.id)) pen += 0.3;
      }
      for (let pi = 0; pi < people.length; pi++) {
        const dev = dayK[pi] / people[pi].kcal - 1;
        pen += 25 * dev * dev;
      }
      // разнообразие внутри дня и между соседними днями
      const L = recipes[day[1]], D = recipes[day[2]];
      if (L.pr === D.pr && !['veg', 'dairy'].includes(L.pr)) pen += 1.5;
      if (L.b === D.b) pen += 1;
      if (d > 0) {
        const prev = plan[d - 1];
        if (recipes[prev[0]].b === recipes[day[0]].b) pen += 0.8;
        if (recipes[prev[2]].pr === D.pr) pen += 0.8;
        if (recipes[prev[1]].pr === L.pr) pen += 0.5;
        if (recipes[prev[3]].b === recipes[day[3]].b) pen += 0.3;
      }
    }
    for (const n of used.values()) if (n > 1) pen += 6 * (n - 1);
    // нормы в среднем за период
    for (let pi = 0; pi < people.length; pi++) {
      const t = people[pi], a = per[pi];
      const short = (v, target, w) => {
        const r = v / days / target;
        if (r < 1) pen += w * (1 - r) * (1 - r);
      };
      short(a.p, t.p, 12); short(a.fb, t.fb, 8); short(a.vc, t.vc, 6);
      short(a.ca, t.ca, 6); short(a.fe, t.fe, 6); short(a.vf, t.vf, 8);
      const fat = a.f / days;
      if (fat > t.fatMax) pen += 20 * Math.pow(fat / t.fatMax - 1, 2);
      if (fat < t.fatMin) pen += 10 * Math.pow(1 - fat / t.fatMin, 2);
    }
    const fishNeed = Math.max(1, Math.round((2 * days) / 7));
    if (fish < fishNeed && ctx.pools.d.some((i) => recipes[i].pr === 'fish')) pen += 2 * (fishNeed - fish);
    // бюджет
    if (budget > 0) {
      const over = cost / budget - 1;
      if (over > 0) pen += 200 * over + 2000 * over * over;
      pen += 0.05 * (cost / budget); // при выполненных нормах деньги — не главное: экономия лишь при равенстве
    }
    return { pen, cost };
  }

  // ── Отжиг ──
  function rng(seed) {
    let s = seed >>> 0 || 1;
    return () => {
      s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0;
      return s / 4294967296;
    };
  }

  function randomPlan(ctx, rand) {
    const plan = [];
    const taken = new Set();
    for (let d = 0; d < ctx.days; d++) {
      const day = [];
      for (const s of SLOTS) {
        const pool = ctx.pools[s];
        let pick = pool[Math.floor(rand() * pool.length)];
        for (let t = 0; t < 10 && taken.has(pick); t++) pick = pool[Math.floor(rand() * pool.length)];
        taken.add(pick);
        day.push(pick);
      }
      plan.push(day);
    }
    return plan;
  }

  function anneal(ctx, budget, rand, start, iters) {
    let plan = start ? start.map((d) => d.slice()) : randomPlan(ctx, rand);
    let cur = evaluate(ctx, plan, budget);
    let best = { plan: plan.map((d) => d.slice()), ...cur };
    const T0 = 3, T1 = 0.01;
    for (let it = 0; it < iters; it++) {
      const T = T0 * Math.pow(T1 / T0, it / iters);
      const d = Math.floor(rand() * ctx.days);
      const si = Math.floor(rand() * 4);
      const old = plan[d][si];
      let swapD = -1;
      if (rand() < 0.25 && ctx.days > 1) {
        swapD = Math.floor(rand() * ctx.days);
        plan[d][si] = plan[swapD][si];
        plan[swapD][si] = old;
      } else {
        const pool = ctx.pools[SLOTS[si]];
        plan[d][si] = pool[Math.floor(rand() * pool.length)];
      }
      const next = evaluate(ctx, plan, budget);
      if (next.pen <= cur.pen || rand() < Math.exp((cur.pen - next.pen) / T)) {
        cur = next;
        if (cur.pen < best.pen) best = { plan: plan.map((x) => x.slice()), ...cur };
      } else if (swapD >= 0) {
        plan[swapD][si] = plan[d][si];
        plan[d][si] = old;
      } else {
        plan[d][si] = old;
      }
    }
    return best;
  }

  // ── Список покупок ──
  function totalsForPlan(ctx, plan) {
    const grams = {};
    const daysOut = [];
    const nutr = ctx.people.map(() => ({ k: 0, p: 0, f: 0, c: 0, fb: 0, vc: 0, ca: 0, fe: 0, vf: 0 }));
    for (let d = 0; d < ctx.days; d++) {
      const meals = [];
      for (let si = 0; si < 4; si++) {
        const slot = SLOTS[si];
        const r = ctx.recipes[plan[d][si]];
        const mults = ctx.people.map((p) => portion(ctx, r, slot, p));
        const mult = mults.reduce((a, b) => a + b, 0);
        for (const [id, g] of Object.entries(r.i)) grams[id] = (grams[id] || 0) + g * mult;
        ctx.people.forEach((_, pi) => {
          for (const k of Object.keys(nutr[pi])) nutr[pi][k] += r.nut[k] * mults[pi];
        });
        meals.push({ slot, slotName: SLOT_NAMES[slot], recipe: r, mults, mult });
      }
      daysOut.push(meals);
    }
    for (const n of nutr) for (const k of Object.keys(n)) n[k] /= ctx.days;
    return { grams, days: daysOut, nutrition: nutr };
  }

  // лучшая покупка нужного количества в одном магазине
  function bestBuy(list, need) {
    let best = null;
    for (const it of list) {
      let packs, cost, qty;
      if (it.w) {
        qty = Math.max(0.1, Math.ceil(need * 10 - 1e-9) / 10);
        packs = 1; cost = qty * it.p / it.q;
      } else {
        packs = Math.max(1, Math.ceil(need / it.q - 1e-9));
        qty = packs * it.q; cost = packs * it.p;
      }
      if (!best || cost < best.cost) best = { item: it, packs, qty, cost };
    }
    return best;
  }

  function baselineBuy(prod, need) {
    if (prod.wt) {
      const qty = Math.max(0.1, Math.ceil(need * 10 - 1e-9) / 10);
      return { item: { t: prod.n, p: prod.bp, q: 1, w: true }, packs: 1, qty, cost: qty * prod.bp, approx: true };
    }
    const packs = Math.max(1, Math.ceil(need / prod.pk - 1e-9));
    return { item: { t: prod.n, p: prod.bp * prod.pk, q: prod.pk }, packs, qty: packs * prod.pk, cost: packs * prod.pk * prod.bp, approx: true };
  }

  function combos(arr, k) {
    const out = [];
    const rec = (start, cur) => {
      if (cur.length) out.push(cur.slice());
      if (cur.length === k) return;
      for (let i = start; i < arr.length; i++) { cur.push(arr[i]); rec(i + 1, cur); cur.pop(); }
    };
    rec(0, []);
    return out;
  }

  function shoppingList(ctx, grams, storeIds, maxStores) {
    const needs = [];
    const fromPantry = [];
    for (const [id, g] of Object.entries(grams)) {
      const prod = ctx.P[id];
      const need = gramsToUnits(prod, g);
      if (ctx.pantry.has(id)) { fromPantry.push({ prod, need, grams: g }); continue; }
      const opts = {};
      for (const [sid, list] of Object.entries(ctx.priceIdx[id].perStore)) opts[sid] = bestBuy(list, need);
      needs.push({ prod, need, grams: g, opts, base: baselineBuy(prod, need) });
    }
    const liveStores = (storeIds || []).filter((sid) => needs.some((n) => n.opts[sid]));
    const k = Math.max(1, Math.min(+maxStores || liveStores.length || 1, liveStores.length || 1));
    let bestCombo = [], bestTotal = Infinity;
    const candidates = liveStores.length ? combos(liveStores, k) : [[]];
    for (const combo of candidates) {
      let total = 0;
      for (const n of needs) {
        let c = n.base.cost;
        for (const sid of combo) if (n.opts[sid] && n.opts[sid].cost < c) c = n.opts[sid].cost;
        total += c;
      }
      if (total < bestTotal - 0.01 || (Math.abs(total - bestTotal) < 0.01 && combo.length < bestCombo.length)) {
        bestTotal = total; bestCombo = combo;
      }
    }
    const lines = needs.map((n) => {
      let pick = { store: null, ...n.base };
      for (const sid of bestCombo) {
        const o = n.opts[sid];
        if (o && o.cost < pick.cost) pick = { store: sid, ...o, approx: false };
      }
      // если живых цен в выбранных магазинах нет, но есть в других — показать ориентир
      return { prod: n.prod, need: n.need, grams: n.grams, ...pick, left: Math.max(0, pick.qty - n.need) };
    });
    lines.sort((a, b) => (a.store || '~').localeCompare(b.store || '~') || a.prod.n.localeCompare(b.prod.n, 'ru'));
    const total = lines.reduce((s, l) => s + l.cost, 0);
    return { lines, total, stores: bestCombo, fromPantry };
  }

  // ── Главная функция ──
  function plan(data, opts) {
    const ctx = makeContext(data, opts);
    if (!ctx.pools.b.length || !ctx.pools.l.length || !ctx.pools.d.length || !ctx.pools.k.length) {
      return { error: 'С такими ограничениями не осталось рецептов на все приёмы пищи. Уберите часть ограничений.' };
    }
    const budget = +opts.budget || 0;
    const rand = rng(opts.seed || Date.now());
    const iters = opts.iterations || 25000;
    let target = budget;
    let best = null, result = null;
    for (let round = 0; round < 10; round++) {
      let cand = null;
      for (let rs = 0; rs < 2; rs++) {
        const r = anneal(ctx, target, rand, rs === 0 && best ? best.plan : null, iters);
        if (!cand || r.pen < cand.pen) cand = r;
      }
      const tot = totalsForPlan(ctx, cand.plan);
      const shop = shoppingList(ctx, tot.grams, opts.stores, opts.maxStores);
      const res = { plan: cand.plan, totals: tot, shop, pen: cand.pen };
      if (!result || (shop.total <= budget && (result.shop.total > budget || res.pen < result.pen)) ||
          (result.shop.total > budget && shop.total < result.shop.total)) result = res;
      best = cand;
      if (!budget || shop.total <= budget) break;
      target = target * Math.min(0.95, budget / shop.total);
    }
    const t = result.totals;
    return {
      days: t.days,
      nutrition: t.nutrition,
      targets: ctx.people,
      shop: result.shop,
      budget,
      overBudget: budget > 0 && result.shop.total > budget,
      livePriceShare: share(ctx, t.grams),
      recipeIds: [...new Set(t.days.flat().map((m) => m.recipe.id))],
    };
  }

  function share(ctx, grams) {
    let all = 0, live = 0;
    for (const [id, g] of Object.entries(grams)) {
      if (ctx.pantry.has(id)) continue;
      const c = ctx.gramCost[id] * g;
      all += c;
      if (ctx.priceIdx[id].live) live += c;
    }
    return all ? live / all : 0;
  }

  const api = { plan, personTargets, recipeNutrition, gramsToUnits, buildPriceIndex, shoppingList, DIETS, SLOT_NAMES, SLOTS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Planner = api;
})(typeof window !== 'undefined' ? window : globalThis);
