/* Интерфейс: форма, запуск подбора, вывод меню, покупок и цен. */
(function () {
  'use strict';

  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const rub = (v) => Math.round(v).toLocaleString('ru-RU') + ' ₽';
  const store = {
    get(k, d) { try { const v = localStorage.getItem('eat.' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('eat.' + k, JSON.stringify(v)); } catch (e) { /* приватный режим */ } },
  };

  const STORE_ORDER = ['pyaterochka', 'magnit', 'chizhik', 'perekrestok', 'lenta', 'metro', 'auchan', 'vkusvill', 'dixy'];
  const STORE_NAMES = { pyaterochka: 'Пятёрочка', magnit: 'Магнит', chizhik: 'Чижик', perekrestok: 'Перекрёсток', lenta: 'Лента', metro: 'Метро', auchan: 'Ашан', vkusvill: 'ВкусВилл', dixy: 'Дикси' };
  const ACT = [[1.2, 'Сидячий'], [1.375, 'Лёгкая'], [1.55, 'Средняя'], [1.725, 'Высокая']];
  const GOALS = [['keep', 'Держать вес'], ['lose', 'Худеть'], ['gain', 'Набирать']];
  const UNIT = { kg: 'кг', l: 'л', pc: 'шт' };

  let data = { products: [], recipes: [], prices: null };
  let P = {};
  let last = null;

  async function loadJSON(url, fallback) {
    try {
      const r = await fetch(url, { cache: 'no-cache' });
      if (!r.ok) throw new Error(r.status);
      return await r.json();
    } catch (e) {
      return fallback;
    }
  }

  // ── Форма ──
  function personRow(p) {
    const div = document.createElement('div');
    div.className = 'person';
    const opt = (list, v) => list.map(([k, n]) => `<option value="${k}"${String(k) === String(v) ? ' selected' : ''}>${n}</option>`).join('');
    div.innerHTML = `
      <label class="field"><span>Пол</span><select name="sex">${opt([['m', 'М'], ['f', 'Ж']], p.sex)}</select></label>
      <label class="field"><span>Возраст</span><input name="age" type="number" inputmode="numeric" min="3" max="100" value="${p.age}"></label>
      <label class="field"><span>Вес, кг</span><input name="weight" type="number" inputmode="numeric" min="15" max="250" value="${p.weight}"></label>
      <label class="field"><span>Рост, см</span><input name="height" type="number" inputmode="numeric" min="90" max="230" value="${p.height}"></label>
      <label class="field"><span>Активность</span><select name="activity">${opt(ACT, p.activity)}</select></label>
      <label class="field"><span>Цель</span><select name="goal">${opt(GOALS, p.goal)}</select></label>
      <button type="button" class="rm ghost" aria-label="Убрать">✕</button>`;
    div.querySelector('.rm').onclick = () => { if ($('#people').children.length > 1) div.remove(); };
    return div;
  }

  function chip(name, value, label, checked, sub) {
    return `<label class="chip"><input type="checkbox" name="${name}" value="${esc(value)}"${checked ? ' checked' : ''}><span>${esc(label)}${sub ? `<small>${esc(sub)}</small>` : ''}</span></label>`;
  }

  function ago(iso) {
    if (!iso) return '';
    const h = (Date.now() - new Date(iso).getTime()) / 3.6e6;
    if (h < 1) return 'цены свежие';
    if (h < 24) return `цены ${Math.round(h)} ч назад`;
    return `цены ${Math.round(h / 24)} дн назад`;
  }

  function renderForm(saved) {
    $('#days').innerHTML = Array.from({ length: 14 }, (_, i) => `<option value="${i + 1}">${i + 1} ${i === 0 ? 'день' : i < 4 ? 'дня' : 'дней'}</option>`).join('');
    $('#days').value = saved.days || 7;
    $('#budget').value = saved.budget || 5000;
    $('#maxStores').value = saved.maxStores || 2;
    const people = saved.people && saved.people.length ? saved.people : [{ sex: 'm', age: 30, weight: 75, height: 178, activity: 1.375, goal: 'keep' }];
    people.forEach((p) => $('#people').appendChild(personRow(p)));

    const ps = (data.prices && data.prices.stores) || {};
    const ids = STORE_ORDER.filter((id) => ps[id]).concat(Object.keys(ps).filter((id) => !STORE_ORDER.includes(id)));
    const chosen = saved.stores || ids;
    $('#stores').innerHTML = ids.length
      ? ids.map((id) => chip('store', id, ps[id].name || STORE_NAMES[id] || id, chosen.includes(id), `${ps[id].found} товаров · ${ago(ps[id].updated)}`)).join('')
      : '';
    const info = $('#pricesInfo');
    if (!ids.length) {
      info.className = 'hint warn';
      info.textContent = 'Живых цен пока нет — считаю по ориентировочным. Запустите сборщик цен (см. README), и здесь появятся сети.';
    } else {
      const missing = STORE_ORDER.filter((id) => !ps[id]).map((id) => STORE_NAMES[id]);
      info.className = 'hint';
      info.textContent = missing.length ? `Нет цен: ${missing.join(', ')}. Товары без живой цены считаются по ориентиру (≈).` : '';
    }

    $('#diets').innerHTML = Object.entries(Planner.DIETS).map(([k, d]) => chip('diet', k, d.name, (saved.diets || []).includes(k))).join('');
    $('#pantry').innerHTML = data.products.filter((p) => p.pantry).map((p) => chip('pantry', p.id, p.n, (saved.pantry || []).includes(p.id))).join('');
    $('#dislikes').innerHTML = data.products.slice().sort((a, b) => a.n.localeCompare(b.n, 'ru'))
      .map((p) => chip('dislike', p.id, p.n, (saved.dislikes || []).includes(p.id))).join('');
  }

  function readForm() {
    const vals = (name) => [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((i) => i.value);
    const people = [...$('#people').children].map((row) => {
      const g = (n) => row.querySelector(`[name="${n}"]`).value;
      return { sex: g('sex'), age: +g('age'), weight: +g('weight'), height: +g('height'), activity: +g('activity'), goal: g('goal') };
    });
    return {
      budget: +$('#budget').value, days: +$('#days').value, maxStores: +$('#maxStores').value,
      people, stores: vals('store'), diets: vals('diet'), pantry: vals('pantry'), dislikes: vals('dislike'),
    };
  }

  // ── Расчёт ──
  function run() {
    const opts = readForm();
    store.set('settings', opts);
    const btn = $('#go');
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span>Подбираю…';
    setTimeout(() => {
      try {
        const history = store.get('history', []);
        // прошлое меню штрафуется, поэтому каждый новый подбор — с другими блюдами
        const res = Planner.plan(data, Object.assign({}, opts, { history, seed: Date.now() }));
        if (res.error) { alert(res.error); return; }
        store.set('history', res.recipeIds);
        store.set('checked', {});
        last = { res, opts };
        render();
      } finally {
        btn.disabled = false;
        btn.textContent = 'Подобрать рацион';
        $('#again').hidden = false;
      }
    }, 30);
  }

  // ── Вывод ──
  function render() {
    const { res, opts } = last;
    $('#result').hidden = false;
    renderSummary(res, opts);
    renderMenu(res, opts);
    renderShop(res);
    renderPrices(res, opts);
    $('#result').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderSummary(res, opts) {
    const pct = res.budget ? Math.min(100, (100 * res.shop.total) / res.budget) : 0;
    const t = res.targets[0], n = res.nutrition[0];
    const bar = (label, v, target, unit, fmt) => {
      const r = v / target;
      return `<div class="nut${r < 0.9 ? ' low' : ''}"><span>${label}</span><b>${fmt ? fmt(v) : Math.round(v)} ${unit} <small>/ ${Math.round(target)}</small></b>
        <div class="bar"><i style="width:${Math.min(100, r * 100)}%"></i></div></div>`;
    };
    const fatPct = (n.f * 9) / n.k * 100;
    const live = Math.round(res.livePriceShare * 100);
    const stores = res.shop.stores.map((s) => STORE_NAMES[s] || s).join(', ');
    $('#summary').innerHTML = `
      <h2>${rub(res.shop.total)} <small style="font-weight:400;color:var(--muted)">из ${rub(res.budget)}</small></h2>
      <div class="budgetbar${res.overBudget ? ' over' : ''}"><i style="width:${pct}%"></i></div>
      <p class="sub">${opts.days} ${opts.days === 1 ? 'день' : opts.days < 5 ? 'дня' : 'дней'} · ${opts.people.length} чел. · ${stores ? 'магазины: ' + stores : 'цены ориентировочные'} · живые цены: ${live}% суммы</p>
      ${res.overBudget ? `<p class="note">Бюджета не хватает даже на самый экономный полноценный рацион. Минимум на этот состав — около ${rub(res.shop.total)}. Можно сократить число дней, убрать ограничения или разрешить больше магазинов.</p>` : ''}
      <div class="people-k">${res.targets.map((tt, i) => `Человек ${i + 1}: ${Math.round(res.nutrition[i].k)} из ${tt.kcal} ккал/день`).join(' · ')}</div>
      <div class="nutr">
        ${bar('Белок', n.p, t.p, 'г')}
        <div class="nut${fatPct > 35 ? ' low' : ''}"><span>Жиры</span><b>${Math.round(fatPct)}% ккал <small>/ 20–35%</small></b><div class="bar"><i style="width:${Math.min(100, fatPct / 35 * 100)}%"></i></div></div>
        ${bar('Клетчатка', n.fb, t.fb, 'г')}
        ${bar('Овощи и фрукты', n.vf, t.vf, 'г')}
        ${bar('Витамин C', n.vc, t.vc, 'мг')}
        ${bar('Кальций', n.ca, t.ca, 'мг')}
        ${bar('Железо', n.fe, t.fe, 'мг', (v) => v.toFixed(1))}
      </div>
      <p class="hint">В среднем за день, для человека 1. Порции каждого рассчитаны под его норму калорий.</p>`;
  }

  function renderMenu(res, opts) {
    const start = new Date();
    $('#tab-menu').innerHTML = res.days.map((meals, d) => {
      const date = new Date(start.getTime() + d * 864e5).toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
      const kcal = meals.reduce((s, m) => s + m.recipe.nut.k * m.mults[0], 0);
      return `<div class="card day"><h3>День ${d + 1} <small>${date} · ${Math.round(kcal)} ккал</small></h3>
        ${meals.map((m, i) => `<div class="meal" data-d="${d}" data-m="${i}" role="button" tabindex="0">
          <span class="slot">${m.slotName}</span><span class="name">${esc(m.recipe.n)}</span>
          <span class="meta">${Math.round(m.recipe.nut.k * m.mults[0])} ккал · ${m.recipe.min} мин</span></div>`).join('')}
      </div>`;
    }).join('');
    $('#tab-menu').querySelectorAll('.meal').forEach((el) => {
      const open = () => showRecipe(res.days[+el.dataset.d][+el.dataset.m], opts);
      el.onclick = open;
      el.onkeydown = (e) => { if (e.key === 'Enter') open(); };
    });
  }

  function showRecipe(m, opts) {
    const r = m.recipe;
    const people = opts.people.length;
    const ing = Object.entries(r.i).map(([id, g]) => {
      const p = P[id];
      const total = g * m.mult;
      let amount = total >= 1000 ? (total / 1000).toFixed(2).replace(/\.?0+$/, '') + ' кг' : Math.round(total) + ' г';
      if (p.u === 'pc') amount = `${(total / p.pcg).toFixed(1).replace(/\.0$/, '')} шт`;
      if (p.u === 'l') amount = total >= 1000 ? (total / 1000).toFixed(2) + ' л' : Math.round(total) + ' мл';
      return `<li>${esc(p.n)} — ${amount}</li>`;
    }).join('');
    const portions = m.mults.map((x, i) => `человек ${i + 1}: ${Math.round(r.nut.k * x)} ккал`).join(', ');
    $('#recipeBody').innerHTML = `<h2>${esc(r.n)}</h2>
      <p class="hint">${m.slotName} · ${r.min} мин · на ${people} чел. (${portions})</p>
      <p class="hint">На 1 порцию 100%: Б ${Math.round(r.nut.p)} г · Ж ${Math.round(r.nut.f)} г · У ${Math.round(r.nut.c)} г · ${Math.round(r.nut.k)} ккал</p>
      <h3>Продукты на всех</h3><ul>${ing}</ul>
      <h3>Как готовить</h3><ol>${r.s.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>
      <p class="hint">Соль и специи — по вкусу.</p>`;
    $('#recipe').showModal();
  }

  function qtyText(prod, line) {
    const u = UNIT[prod.u];
    if (line.item.w) return `${line.qty.toFixed(1)} ${u}`;
    const q = line.item.q;
    const pack = prod.u === 'pc' ? `${q} шт` : q < 1 ? `${Math.round(q * 1000)} ${prod.u === 'l' ? 'мл' : 'г'}` : `${q} ${u}`;
    return `${line.packs} × ${pack}`;
  }

  function renderShop(res) {
    const checked = store.get('checked', {});
    const groups = {};
    for (const l of res.shop.lines) (groups[l.store || '~'] = groups[l.store || '~'] || []).push(l);
    const html = Object.entries(groups).map(([sid, lines]) => {
      const title = sid === '~' ? 'Любой магазин (цена ориентировочная)' : STORE_NAMES[sid] || sid;
      const sum = lines.reduce((s, l) => s + l.cost, 0);
      return `<div class="card store"><h3><span>${esc(title)}</span><span>${rub(sum)}</span></h3>
        ${lines.map((l) => {
          const key = l.prod.id;
          const left = l.left > 0.001 && !l.item.w ? ` · останется ${l.prod.u === 'pc' ? Math.round(l.left) + ' шт' : l.left < 1 ? Math.round(l.left * 1000) + (l.prod.u === 'l' ? ' мл' : ' г') : l.left.toFixed(1) + ' ' + UNIT[l.prod.u]}` : '';
          return `<label class="line${checked[key] ? ' done' : ''}"><input type="checkbox" data-k="${key}"${checked[key] ? ' checked' : ''}>
            <span class="what"><b>${esc(l.prod.n)}</b> — ${qtyText(l.prod, l)}<br><span class="t">${esc(l.approx ? 'ориентир, конкретный товар выберите сами' : l.item.t)}${left}</span></span>
            <span class="sum${l.approx ? ' approx' : ''}">${l.approx ? '≈ ' : ''}${rub(l.cost)}</span></label>`;
        }).join('')}</div>`;
    }).join('');
    const pantry = res.shop.fromPantry.length
      ? `<p class="hint">Из запасов дома: ${res.shop.fromPantry.map((x) => x.prod.n).join(', ')}. Соль и специи — тоже свои.</p>` : '<p class="hint">Соль и специи в список не входят.</p>';
    $('#tab-shop').innerHTML = html + pantry;
    $('#tab-shop').querySelectorAll('input[data-k]').forEach((cb) => {
      cb.onchange = () => {
        const c = store.get('checked', {});
        c[cb.dataset.k] = cb.checked;
        store.set('checked', c);
        cb.closest('.line').classList.toggle('done', cb.checked);
      };
    });
  }

  function renderPrices(res, opts) {
    const ps = (data.prices && data.prices.stores) || {};
    const sids = STORE_ORDER.filter((id) => ps[id]).concat(Object.keys(ps).filter((id) => !STORE_ORDER.includes(id)));
    if (!sids.length) {
      $('#tab-prices').innerHTML = '<div class="card"><p>Живых цен пока нет. Таблица появится после первого запуска сборщика.</p></div>';
      return;
    }
    const used = new Set(res.shop.lines.map((l) => l.prod.id));
    const rows = data.products.filter((p) => used.has(p.id)).map((p) => {
      const items = (data.prices.items && data.prices.items[p.id]) || {};
      const per = sids.map((sid) => (items[sid] && items[sid].length ? Math.min(...items[sid].map((it) => it.p / it.q)) : null));
      const min = Math.min(...per.filter((x) => x != null));
      return `<tr><td>${esc(p.n)} <span class="hint">₽/${UNIT[p.u]}</span></td>${per.map((v, i) => {
        const title = v != null ? items[sids[i]].map((it) => it.t).join('\n') : '';
        return `<td class="${v != null && v === min ? 'best' : ''}" title="${esc(title)}">${v != null ? (p.u === 'pc' ? v.toFixed(1) : Math.round(v)) : '—'}</td>`;
      }).join('')}</tr>`;
    }).join('');
    $('#tab-prices').innerHTML = `<div class="card scroll"><table class="ptable"><thead><tr><th>Продукт</th>${sids.map((s) => `<th>${esc(ps[s].name || STORE_NAMES[s] || s)}</th>`).join('')}</tr></thead>
      <tbody>${rows}</tbody></table>
      <p class="hint">Лучшая цена за кг/л/шт среди найденных товаров. Обновление: ${sids.map((s) => `${ps[s].name || s} — ${new Date(ps[s].updated).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`).join('; ')}.</p></div>`;
  }

  // prices.json собирается на компьютере, prices.ci.json — GitHub Actions (только Магнит). По каждой сети берём более свежие.
  function mergePrices(...sources) {
    const out = { stores: {}, items: {} };
    for (const src of sources) {
      if (!src || !src.stores) continue;
      for (const [sid, info] of Object.entries(src.stores)) {
        const cur = out.stores[sid];
        if (cur && new Date(cur.updated) >= new Date(info.updated)) continue;
        out.stores[sid] = info;
        for (const per of Object.values(out.items)) delete per[sid];
        for (const [pid, per] of Object.entries(src.items || {})) {
          if (per[sid]) (out.items[pid] = out.items[pid] || {})[sid] = per[sid];
        }
      }
    }
    return Object.keys(out.stores).length ? out : null;
  }

  function tabs() {
    document.querySelectorAll('.tabs button').forEach((b) => {
      b.onclick = () => {
        document.querySelectorAll('.tabs button').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
        document.querySelectorAll('.tab').forEach((t) => { t.hidden = t.id !== 'tab-' + b.dataset.tab; });
      };
    });
  }

  async function init() {
    const [products, recipes, local, ci] = await Promise.all([
      loadJSON('data/products.json', []), loadJSON('data/recipes.json', []),
      loadJSON('data/prices.json', null), loadJSON('data/prices.ci.json', null),
    ]);
    const prices = mergePrices(local, ci);
    if (!products.length || !recipes.length) {
      document.querySelector('main').innerHTML = '<div class="card"><p>Не удалось загрузить данные. Откройте приложение через сервер: <code>python -m collector serve</code> (просто открыть файл index.html нельзя).</p></div>';
      return;
    }
    data = { products, recipes, prices };
    P = Object.fromEntries(products.map((p) => [p.id, p]));
    renderForm(store.get('settings', {}));
    $('#addPerson').onclick = () => $('#people').appendChild(personRow({ sex: 'f', age: 30, weight: 62, height: 166, activity: 1.375, goal: 'keep' }));
    $('#form').onsubmit = (e) => { e.preventDefault(); run(); };
    $('#again').onclick = () => run();
    tabs();
  }

  init();
})();
