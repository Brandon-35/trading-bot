(function () {
'use strict';
const LC = window.LightweightCharts;
const TZ = 7 * 3600; // Asia/Ho_Chi_Minh; chart times are shifted so UTC labels read as local
const C = { up: '#0ecb81', dn: '#f6465d', acc: '#fcd535', mut: '#848e9c', line: '#2b3139', tx: '#eaecef' };
const $ = (s) => document.querySelector(s);

// ---------- helpers ----------
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
const num = (v) => typeof v === 'number' && isFinite(v);
// ---- shared number formatters (vi-VN: "." thousands, "," decimal) ----
const NFS = {};
function nf(min, max) { const k = min + '_' + max; return NFS[k] || (NFS[k] = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: min, maximumFractionDigits: max })); }
const SIG6 = new Intl.NumberFormat('vi-VN', { maximumSignificantDigits: 6 });
const MINUS = '−';
const signOf = (v, sign) => (v < 0 ? MINUS : sign && v > 0 ? '+' : '');
function fnum(v, d) { return num(v) ? nf(d == null ? 2 : d, d == null ? 2 : d).format(v) : '-'; }
function qty(v) { return num(v) ? nf(0, 8).format(v) : '-'; }
function pct(v, o) { o = o || {}; return num(v) ? signOf(v, o.sign) + nf(o.d == null ? 2 : o.d, o.d == null ? 2 : o.d).format(Math.abs(v)) + '%' : '-'; }
function rr(v) { return num(v) ? signOf(v, true) + nf(2, 2).format(Math.abs(v)) + 'R' : '-'; }
// coin prices stay in USDT: by magnitude
function pxDec(p) { return !num(p) ? 2 : p >= 1000 ? 2 : p >= 1 ? 4 : 6; }
function px(v) { return !num(v) ? '-' : Math.abs(v) >= 1 ? fnum(v, pxDec(v)) : SIG6.format(v); }
// ---- money: USDT or VND at the Binance P2P rate ----
let unit = localStorage.getItem('unit') === 'vnd' ? 'vnd' : 'usdt';
let fx = null;
const rate = () => (unit === 'vnd' && fx && fx.usdt_vnd) || 0;
// o: sign (+/- prefix), d (USDT decimals), unit (append "USDT"), compact (VND >= 1 million as "x tr")
function money(v, o) {
  o = o || {};
  if (!num(v)) return '-';
  const r = rate();
  if (r) {
    const x = v * r, a = Math.abs(x);
    return signOf(Math.round(x) === 0 ? 0 : x, o.sign) + (o.compact && a >= 1e6 ? nf(0, 1).format(a / 1e6) + ' tr' : nf(0, 0).format(a)) + ' ₫';
  }
  const a = Math.abs(v), d = o.d != null ? o.d : a > 0 && a < 1 ? 4 : 2;
  return signOf(v, o.sign) + nf(d, d).format(a) + (o.unit ? ' USDT' : '');
}
function axisMoney(v) { // chart price-scale label
  const r = rate();
  if (!r) return fnum(v, 2);
  const x = v * r, a = Math.abs(x);
  return (x < 0 ? MINUS : '') + (a >= 1e6 ? nf(0, 1).format(a / 1e6) + ' tr' : nf(0, 0).format(a));
}
function cls(v) { return !num(v) || v === 0 ? '' : v > 0 ? 'up' : 'dn'; }
const pnl = (v, o) => el('span', cls(v), money(v, Object.assign({ sign: true }, o)));
const pctEl = (v) => el('span', cls(v), pct(v, { sign: true }));
const rEl = (v) => el('span', cls(v), rr(v));
function vd(t) { return num(t) ? new Date((t + TZ) * 1000).toISOString().slice(0, 10).split('-').reverse().join('/') : '-'; }
function vt(t) { // "11-27 14:00"
  if (!num(t)) return '-';
  return new Date((t + TZ) * 1000).toISOString().slice(5, 16).replace('T', ' ');
}
function short(sym) { return String(sym || '').replace(/\/?USDT(:USDT)?$/, ''); }
const VI = { long: 'MUA/LONG', buy: 'MUA', short: 'BÁN/SHORT', sell: 'BÁN', close: 'ĐÓNG', hold: 'GIỮ', stop_loss: 'Cắt lỗ', take_profit: 'Chốt lời', llm_close: 'AI đóng' };
function badge(text, c) { const k = String(text).toLowerCase(); return el('span', 'badge ' + (c || k), VI[k] || String(text).replace(/_/g, ' ')); }
function empty(title, sub) {
  const d = el('div', 'empty');
  d.appendChild(el('b', null, title));
  if (sub) d.appendChild(document.createTextNode(sub));
  return d;
}
function panel(title, sub) {
  const p = el('div', 'panel'), h = el('div', 'ph');
  h.appendChild(el('span', null, title));
  p.appendChild(h);
  if (sub) p.appendChild(el('div', 'hint', sub));
  p.head = h;
  return p;
}
function card(label, value, sub, hint) {
  const c = el('div', 'card');
  c.appendChild(el('div', 'l', label));
  const v = el('div', 'v');
  if (value instanceof Node) v.appendChild(value); else v.textContent = value;
  c.appendChild(v);
  if (sub != null) { const s = el('div', 's'); if (sub instanceof Node) s.appendChild(sub); else s.textContent = sub; c.appendChild(s); }
  if (hint) c.appendChild(el('div', 'hint', hint));
  return c;
}
// cols: [{h, f(row)->string|Node, l:true left align, k: sort key, t: card title, m: card main value}]
// One table renders both ways: a normal table on desktop; on phones CSS turns each row into a card using data-label.
function table(cols, rows, opt) {
  opt = opt || {};
  const wrap = el('div', 'tw'), t = el('table', 'cards' + (opt.onSort ? ' sortable' : '')), thead = el('thead'), tr = el('tr');
  const ti = Math.max(0, cols.findIndex((c) => c.t));
  cols.forEach((c) => {
    const th = el('th', (c.l ? 'l ' : '') + (c.k ? 'sort' : ''), c.h);
    if (c.k && opt.onSort) {
      th.tabIndex = 0; th.setAttribute('role', 'button');
      th.addEventListener('click', () => opt.onSort(c));
      th.addEventListener('keydown', (e) => { if (e.key === 'Enter') opt.onSort(c); });
    }
    tr.appendChild(th);
  });
  thead.appendChild(tr); t.appendChild(thead);
  const tb = el('tbody');
  rows.forEach((r) => {
    const row = el('tr');
    cols.forEach((c, i) => {
      const td = el('td', [c.cls || (c.l ? 'l' : ''), i === ti ? 'pt' : '', c.m ? 'pm' : ''].filter(Boolean).join(' '));
      td.dataset.label = String(c.h).replace(/ [▲▼]$/, '');
      const v = c.f(r);
      if (v instanceof Node) td.appendChild(v); else td.textContent = v == null ? '-' : v;
      if (opt.flash) opt.flash(r, c, td);
      row.appendChild(td);
    });
    tb.appendChild(row);
  });
  t.appendChild(tb);
  wrap.appendChild(t);
  return wrap;
}

async function api(path) {
  const r = await fetch(path, { credentials: 'same-origin', redirect: 'manual', headers: { Accept: 'application/json' } });
  if (r.status === 401 || r.type === 'opaqueredirect' || r.redirected || (r.status >= 300 && r.status < 400)) {
    window.location = '/login';
    throw new Error('auth');
  }
  if (!r.ok) throw new Error(path + ' ' + r.status);
  return r.json();
}

// ---------- charts ----------
function mkChart(box, extra) {
  const ch = LC.createChart(box, Object.assign({
    autoSize: true,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: C.mut, fontFamily: '"IBM Plex Sans",system-ui,sans-serif', fontSize: 12 },
    grid: { vertLines: { color: '#1e2329' }, horzLines: { color: '#1e2329' } },
    rightPriceScale: { borderColor: C.line },
    timeScale: { borderColor: C.line, timeVisible: true, secondsVisible: false },
    crosshair: { vertLine: { color: '#5e6673', labelBackgroundColor: '#2b3139' }, horzLine: { color: '#5e6673', labelBackgroundColor: '#2b3139' } },
  }, extra || {}));
  return ch;
}
const monthFmt = (t) => typeof t === 'object' ? t.year + '-' + String(t.month).padStart(2, '0') : String(t).slice(0, 7);
const charts = {}; // id -> {chart, series...}

// ---------- header / live ----------
let lastLive = 0;
function tickLive() {
  const b = $('#live'), s = $('#liveTxt');
  if (!lastLive) { s.textContent = 'đang kết nối...'; return; }
  const age = Math.max(0, Math.round(Date.now() / 1000 - lastLive));
  s.textContent = 'TRỰC TIẾP';
  $('#liveAge').textContent = ' · cập nhật ' + (age < 90 ? age + ' giây' : Math.round(age / 60) + ' phút') + ' trước';
  b.classList.toggle('stale', age > 60);   // bot loop writes every ~20 s, plus slow sync passes
}
setInterval(tickLive, 1000);

// ---------- Overview ----------
function buildOverview() {
  const root = $('#tab-overview');
  root.appendChild(el('div', 'grid')).id = 'kpis';
  const p1 = panel('Giá trị của bot', 'Tổng tiền của bot theo thời gian (USDT). Xanh = đang lãi so với vốn ban đầu, đỏ = đang lỗ.');
  const b1 = el('div', 'chart'); p1.appendChild(b1); root.appendChild(p1);
  const p2 = panel('Lãi/lỗ theo ngày', 'Cột = lãi/lỗ từng ngày (xanh lãi, đỏ lỗ). Đường vàng = tổng cộng dồn từ đầu.');
  const b2 = el('div', 'chart sm'); p2.appendChild(b2); root.appendChild(p2);
  const ch1 = mkChart(b1, { localization: { priceFormatter: axisMoney } });
  const eq = ch1.addSeries(LC.BaselineSeries, {
    baseValue: { type: 'price', price: 0 },
    topLineColor: C.up, topFillColor1: 'rgba(14,203,129,.28)', topFillColor2: 'rgba(14,203,129,.02)',
    bottomLineColor: C.dn, bottomFillColor1: 'rgba(246,70,93,.02)', bottomFillColor2: 'rgba(246,70,93,.28)',
    lineWidth: 2, priceLineVisible: false,
  });
  const ch2 = mkChart(b2, { timeScale: { borderColor: C.line, timeVisible: false }, localization: { priceFormatter: axisMoney } });
  const bars = ch2.addSeries(LC.HistogramSeries, { priceLineVisible: false, lastValueVisible: false });
  const cum = ch2.addSeries(LC.LineSeries, { color: C.acc, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
  charts.overview = { ch1, eq, ch2, bars, cum, b1, b2, p1, p2 };
}
async function loadOverview() {
  const [s, e] = await Promise.all([api('/api/summary'), api('/api/equity')]);
  const k = $('#kpis'); clear(k);
  const st = s.start || {}, nw = s.now || {}, ss = s.stats || {};
  const M = { unit: true, compact: true };
  k.appendChild(card('Vốn ban đầu', money(st.capital, M), 'Futures ' + money(st.futures) + ' + credit AI ' + money(st.llm_credit), 'Số tiền bot bắt đầu chạy, gồm tiền giao dịch và tiền trả cho AI.'));
  k.appendChild(card('Giá trị hiện tại', money(nw.value, M), 'Futures ' + money(nw.futures_value) + ' + AI còn ' + money(nw.llm_remaining), 'Tổng tiền bot đang có bây giờ.'));
  k.appendChild(card('Lãi/lỗ ròng', pnl(nw.pnl, M), pctEl(nw.pnl_pct), 'Hiện tại so với vốn ban đầu. Xanh là lãi, đỏ là lỗ.'));
  k.appendChild(card('Lãi/lỗ hôm nay', pnl(nw.today_pnl, M), null, 'Kết quả riêng của hôm nay.'));
  k.appendChild(card('Tỉ lệ thắng', pct(ss.win_rate), (ss.wins || 0) + ' thắng / ' + (ss.trades || 0) + ' lệnh', 'Trong 100 lệnh đã đóng, có bao nhiêu lệnh có lãi.'));
  k.appendChild(card('Chi phí AI', money(ss.llm_spent, M), 'Còn lại ' + money(nw.llm_remaining) + ' credit', 'Tiền đã trả để AI phân tích thị trường.'));
  k.appendChild(card('Phí + funding', pnl((ss.fees || 0) + (ss.funding || 0), M), 'Phí ' + money(ss.fees, { sign: true }) + ' / funding ' + money(ss.funding, { sign: true }), 'Phí sàn mỗi lệnh và phí giữ vị thế qua đêm.'));
  k.appendChild(card('Sụt giảm tối đa', pct(ss.max_dd_pct), 'Đã chốt ' + money(ss.realized, { sign: true }), 'Mức tụt sâu nhất từ đỉnh. Càng nhỏ càng an toàn.'));
  const o = charts.overview;
  o.eq.applyOptions({ baseValue: { type: 'price', price: st.capital || 0 } });
  const pts = (e.points || []).map((p) => ({ time: p[0] + TZ, value: p[1] }));
  const seen = new Set();
  o.eq.setData(pts.filter((p) => !seen.has(p.time) && seen.add(p.time)));
  const daily = e.daily || [];
  const emptyEq = !pts.length;
  o.b1.style.display = emptyEq ? 'none' : '';
  o.b2.style.display = daily.length ? '' : 'none';
  for (const [pnl, box] of [[o.p1, o.b1], [o.p2, o.b2]]) {
    const old = pnl.querySelector('.empty'); if (old) old.remove();
  }
  if (emptyEq) o.p1.appendChild(empty('Chưa có dữ liệu', 'Biểu đồ sẽ xuất hiện sau vài phút bot chạy.'));
  if (!daily.length) o.p2.appendChild(empty('Chưa có lãi/lỗ theo ngày'));
  let run = 0;
  o.bars.setData(daily.map((d) => ({ time: d[0], value: d[1], color: d[1] >= 0 ? C.up : C.dn })));
  o.cum.setData(daily.map((d) => { run += d[1]; return { time: d[0], value: run }; }));
  setTimeout(() => { o.ch1.timeScale().fitContent(); o.ch2.timeScale().fitContent(); }, 150);
}

// ---------- Positions ----------
const SYMS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT'];
let candleSym = null, liveData = null, prevCells = {}, candleSeries = null, candleChart = null, markerApi = null, priceLines = [];
function buildPositions() {
  const root = $('#tab-positions');
  const p = panel('Vị thế đang mở', 'Các lệnh bot đang giữ, tự làm mới mỗi 5 giây. Ô nhấp nháy vàng = vừa đổi giá.');
  const eqLine = el('small', null, ''); eqLine.id = 'eqLine'; p.head.appendChild(eqLine);
  const body = el('div'); body.id = 'posBody'; p.appendChild(body); root.appendChild(p);
  const cp = panel('Biểu đồ giá', 'Nến 1 giờ. Đường nét đứt: giá vào, cắt lỗ (SL), chốt lời (TP). Mũi tên: điểm bot vào/ra lệnh.');
  const sel = el('select', 'sel'); sel.id = 'symSel';
  SYMS.forEach((s) => { const o = el('option', null, short(s)); o.value = s; sel.appendChild(o); });
  sel.addEventListener('change', () => { candleSym = sel.value; loadCandles(); });
  cp.head.appendChild(sel);
  const box = el('div', 'chart lg'); cp.appendChild(box); root.appendChild(cp);
  candleChart = mkChart(box, { localization: { priceFormatter: px } });
  candleSeries = candleChart.addSeries(LC.CandlestickSeries, { upColor: C.up, downColor: C.dn, borderUpColor: C.up, borderDownColor: C.dn, wickUpColor: C.up, wickDownColor: C.dn });
  markerApi = LC.createSeriesMarkers(candleSeries, []);
}
function renderPositions() {
  const L = liveData; if (!L) return;
  const body = $('#posBody'), pos = L.positions || [];
  document.querySelectorAll('.posCount').forEach((cnt) => { cnt.hidden = !pos.length; cnt.textContent = pos.length; });
  $('#eqLine').textContent = 'Tổng tài sản ' + money(L.equity) + ' · Ví ' + money(L.wallet) + ' · Lãi/lỗ chưa chốt ' + money(L.upnl, { sign: true });
  clear(body);
  if (!pos.length) { body.appendChild(empty('Không có vị thế nào', 'Bot đang đứng ngoài thị trường.')); return; }
  const cur = {};
  const cols = [
    { h: 'Cặp', l: true, f: (r) => short(r.symbol) },
    { h: 'Hướng', f: (r) => badge(r.side) },
    { h: 'Khối lượng', f: (r) => qty(r.qty) },
    { h: 'Giá vào', f: (r) => px(r.entry) },
    { h: 'Giá hiện tại', key: 'mark', f: (r) => px(r.mark) },
    { h: 'Giá thanh lý', f: (r) => px(r.liq) },
    { h: 'Lãi/lỗ chưa chốt (ROE)', key: 'upnl', m: true, f: (r) => { const s = el('span', cls(r.upnl)); s.textContent = money(r.upnl, { sign: true }) + ' (' + pct(r.roe_pct, { sign: true }) + ')'; return s; } },
    { h: 'Cắt lỗ (SL)', f: (r) => px(r.sl) },
    { h: 'Chốt lời (TP)', f: (r) => px(r.tp) },
    { h: 'Mở lúc', f: (r) => vt(r.opened) },
  ];
  body.appendChild(table(cols, pos, { flash: (r, c, td) => {
    if (!c.key) return;
    const id = r.symbol + c.key, v = c.key === 'mark' ? r.mark : r.upnl + '/' + r.roe_pct;
    cur[id] = v;
    if (id in prevCells && prevCells[id] !== v) td.classList.add('flash');
  } }));
  prevCells = Object.assign(prevCells, cur);
}
async function pollLive() {
  try {
    liveData = await api('/api/live');
    lastLive = liveData.ts || Math.floor(Date.now() / 1000);
    tickLive();
    renderPositions();
    if (!candleSym) { candleSym = (liveData.positions[0] && liveData.positions[0].symbol) || SYMS[2]; $('#symSel').value = candleSym; if (currentTab() === 'positions') loadCandles(); }
    if (currentTab() === 'positions') updateLines();
  } catch (e) { if (e.message !== 'auth') $('#live').classList.add('stale'); }
}
function updateLines() {
  priceLines.forEach((l) => candleSeries.removePriceLine(l)); priceLines = [];
  const p = ((liveData && liveData.positions) || []).find((x) => x.symbol === candleSym);
  if (!p) return;
  [['entry', p.entry, C.tx, 'Entry'], ['sl', p.sl, C.dn, 'SL'], ['tp', p.tp, C.up, 'TP']].forEach((x) => {
    if (num(x[1])) priceLines.push(candleSeries.createPriceLine({ price: x[1], color: x[2], lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: x[3] }));
  });
}
let candleFirst = null;
async function loadCandles() {
  if (!candleSym) return;
  const sym = candleSym;
  const d = await api('/api/candles?symbol=' + encodeURIComponent(sym) + '&tf=1h');
  if (sym !== candleSym) return;
  const cs = d.candles || [];
  const last = cs.length ? cs[cs.length - 1][4] : 1;
  const pr = pxDec(last);
  candleSeries.applyOptions({ priceFormat: { type: 'price', precision: pr, minMove: Math.pow(10, -pr) } });
  candleSeries.setData(cs.map((c) => ({ time: c[0] + TZ, open: c[1], high: c[2], low: c[3], close: c[4] })));
  markerApi.setMarkers((d.markers || []).slice().sort((a, b) => a.time - b.time).map((m) => {
    const buy = m.side === 'buy';
    return { time: m.time + TZ, position: buy ? 'belowBar' : 'aboveBar', shape: buy ? 'arrowUp' : 'arrowDown', color: buy ? C.up : C.dn, text: m.label || '' };
  }));
  updateLines();
  if (candleFirst !== sym) { candleChart.timeScale().fitContent(); candleFirst = sym; }
}

// ---------- History ----------
async function loadHistory() {
  const root = $('#tab-history'); const tr = (await api('/api/trades')).slice().sort((a, b) => b.close_time - a.close_time);
  clear(root);
  if (!tr.length) { const p = panel('Lịch sử lệnh', 'Các lệnh bot đã đóng, mới nhất ở trên.'); p.appendChild(empty('Chưa có lệnh nào đã đóng', 'Lệnh sẽ hiện ở đây sau khi bot đóng vị thế.')); root.appendChild(p); return; }
  const sum = (k) => tr.reduce((a, t) => a + (t[k] || 0), 0);
  const g = el('div', 'grid');
  g.appendChild(card('Số lệnh', String(tr.length), null, 'Tổng lệnh đã đóng.'));
  g.appendChild(card('Lệnh thắng', tr.filter((t) => t.net > 0).length + ' / ' + tr.length, null, 'Số lệnh có lãi ròng.'));
  g.appendChild(card('Lãi/lỗ gộp', pnl(sum('pnl')), null, 'Trước khi trừ phí.'));
  g.appendChild(card('Phí', pnl(sum('fees')), null, 'Phí sàn đã trả.'));
  g.appendChild(card('Funding', pnl(sum('funding')), null, 'Phí giữ vị thế qua đêm.'));
  g.appendChild(card('Lãi/lỗ ròng', pnl(sum('net'), { unit: true, compact: true }), null, 'Kết quả thật sau mọi chi phí.'));
  root.appendChild(g);
  const p = panel('Lịch sử lệnh', 'Các lệnh bot đã đóng, mới nhất ở trên. "Ròng" = lãi/lỗ sau khi trừ phí.');
  p.appendChild(table([
    { h: 'Đóng lúc', l: true, f: (t) => vt(t.close_time) },
    { h: 'Cặp', l: true, t: true, f: (t) => { const s = el('span'); s.appendChild(document.createTextNode(short(t.symbol))); if (t.test) s.appendChild(el('span', 'badge test', 'thử')); return s; } },
    { h: 'Hướng', f: (t) => badge(t.side) },
    { h: 'Khối lượng', f: (t) => qty(t.qty) },
    { h: 'Giá vào', f: (t) => px(t.entry) },
    { h: 'Giá ra', f: (t) => px(t.exit) },
    { h: 'Mở lúc', f: (t) => vt(t.open_time) },
    { h: 'Gộp', f: (t) => pnl(t.pnl) },
    { h: 'Phí', f: (t) => pnl(t.fees) },
    { h: 'Funding', f: (t) => pnl(t.funding) },
    { h: 'Ròng', m: true, f: (t) => { const s = pnl(t.net); s.style.fontWeight = 600; return s; } },
    { h: 'Lý do đóng', f: (t) => badge(t.reason || '-') },
  ], tr));
  root.appendChild(p);
}

// ---------- Decisions ----------
let decisions = [], decFilter = 'all';
function renderDecisions() {
  const root = $('#tab-decisions'); clear(root);
  const p = panel('Quyết định của AI', 'AI xem thị trường mỗi giờ rồi chọn: MUA, BÁN, ĐÓNG lệnh hoặc GIỮ nguyên. Bộ kiểm soát rủi ro có thể từ chối.');
  const chips = el('div', 'chips');
  [['all', 'Tất cả'], ['trades', 'Chỉ lệnh'], ['rejected', 'Bị từ chối']].forEach((c) => {
    const b = el('button', 'chip' + (decFilter === c[0] ? ' on' : ''), c[1]); b.type = 'button';
    b.addEventListener('click', () => { decFilter = c[0]; renderDecisions(); });
    chips.appendChild(b);
  });
  p.head.appendChild(chips); root.appendChild(p);
  const rows = decisions.filter((d) => decFilter === 'all' || (decFilter === 'rejected' ? !d.accepted : ['long', 'short', 'close'].includes(d.action)));
  if (!rows.length) { p.appendChild(empty('Không có quyết định nào', decFilter === 'all' ? 'AI chưa đưa ra quyết định nào.' : 'Không có mục nào khớp bộ lọc.')); return; }
  p.appendChild(table([
    { h: 'Thời gian', l: true, f: (d) => vt(d.time) },
    { h: 'Cặp', l: true, t: true, f: (d) => short(d.symbol) },
    { h: 'Hành động', m: true, f: (d) => badge(d.action) },
    { h: 'Độ tự tin', f: (d) => confBar(d.confidence) },
    { h: 'Kết quả', f: (d) => d.accepted ? el('span', 'up', '✓') : el('span', 'dn', d.reject || 'bị từ chối') },
    { h: 'Cắt lỗ (SL)', f: (d) => num(d.sl) ? px(d.sl) : '-' },
    { h: 'Chốt lời (TP)', f: (d) => num(d.tp) ? px(d.tp) : '-' },
    { h: 'Lý do của AI', cls: 'wrap', l: true, f: (d) => d.reason || '-' },
  ], rows));
}
async function loadDecisions() { decisions = (await api('/api/decisions?limit=300')).slice().sort((a, b) => b.time - a.time); renderDecisions(); }

// ---------- Account ----------
let acct = null, symSort = { k: 'net', dir: -1 };
async function loadAccount() { acct = await api('/api/account'); renderAccount(); }
function renderAccount() {
  const root = $('#tab-account'), a = acct; clear(root);
  root.appendChild(el('div', 'banner', 'Toàn bộ tài khoản — gồm cả lệnh bạn tự đánh, không dùng làm vốn của bot.'));
  const cv = a.coverage || {};
  root.appendChild(el('div', 'foot', 'Dữ liệu từ ' + vd(cv.from) + ' đến ' + vd(cv.to) + ' · nguồn: ' + ((cv.sources || []).join(', ').replace('csv', 'file xuất Binance') || '-')));
  const t = a.totals || {}, g = el('div', 'grid');
  const M = { unit: true, compact: true };
  g.appendChild(card('Tiền nạp / chuyển vào', money(t.transfer_in, M), null, 'Tiền bạn đưa vào tài khoản futures.'));
  g.appendChild(card('Tiền rút / chuyển ra', money(t.transfer_out, M), null, 'Tiền bạn lấy ra khỏi futures.'));
  g.appendChild(card('Lãi/lỗ đã chốt', pnl(t.realized, { compact: true }), null, 'Lãi/lỗ của các lệnh đã đóng.'));
  g.appendChild(card('Phí', pnl(t.fees, { compact: true }), null, 'Phí giao dịch đã trả.'));
  g.appendChild(card('Funding', pnl(t.funding, { compact: true }), null, 'Phí giữ vị thế qua đêm.'));
  g.appendChild(card('Bị thanh lý', pnl(t.liquidation, { compact: true }), null, 'Phí thanh lý (quỹ bảo hiểm) khi lệnh bị cháy.'));
  g.appendChild(card('Kết quả giao dịch ròng', pnl(t.net, M), 'Khác (đổi coin…): ' + money(t.other, { sign: true }), 'Đã chốt + phí + funding + thanh lý + khác.'));
  root.appendChild(g);
  const mp = panel('Kết quả theo tháng', 'Cột = kết quả ròng từng tháng, đường vàng = cộng dồn.');
  const mb = el('div', 'chart sm'); mp.appendChild(mb); root.appendChild(mp);
  const mon = a.monthly || [];
  if (!mon.length) { mb.remove(); mp.appendChild(empty('Chưa có dữ liệu theo tháng')); }
  else {
    const mc = mkChart(mb, { timeScale: { borderColor: C.line, timeVisible: false, tickMarkFormatter: monthFmt }, localization: { timeFormatter: monthFmt, priceFormatter: axisMoney } });
    const bars = mc.addSeries(LC.HistogramSeries, { priceLineVisible: false, lastValueVisible: false });
    const cum = mc.addSeries(LC.LineSeries, { color: C.acc, lineWidth: 2, priceLineVisible: false });
    let run = 0;
    bars.setData(mon.map((m) => ({ time: m[0] + '-01', value: m[4], color: m[4] >= 0 ? C.up : C.dn })));
    cum.setData(mon.map((m) => { run += m[4]; return { time: m[0] + '-01', value: run }; }));
    setTimeout(() => mc.timeScale().fitContent(), 150);
  }
  const sp = panel('Theo từng cặp', 'Bấm vào tiêu đề cột để sắp xếp.'); root.appendChild(sp);
  const syms = (a.by_symbol || []).slice().sort((x, y) => symSort.dir * ((x[symSort.k] > y[symSort.k]) - (x[symSort.k] < y[symSort.k])));
  if (!syms.length) sp.appendChild(empty('Chưa có dữ liệu theo cặp'));
  else {
    const col = (h, k, f) => ({ h: h + (symSort.k === k ? (symSort.dir < 0 ? ' ▼' : ' ▲') : ''), k: k, f: f });
    sp.appendChild(table([
      Object.assign(col('Cặp', 'symbol', (r) => r.symbol), { l: true }),
      col('Đã chốt', 'realized', (r) => pnl(r.realized)), col('Phí', 'fees', (r) => pnl(r.fees)),
      col('Funding', 'funding', (r) => pnl(r.funding)), Object.assign(col('Ròng', 'net', (r) => pnl(r.net)), { m: true }), col('Số khớp', 'fills', (r) => String(r.fills)),
    ], syms, { onSort: (c) => { symSort = { k: c.k, dir: symSort.k === c.k ? -symSort.dir : -1 }; renderAccount(); } }));
  }
  const fp = panel('Các lần khớp lệnh gần nhất', 'Tối đa 500 lần khớp. Nhãn "bot" = do bot đặt.'); root.appendChild(fp);
  const fills = (a.fills || []).slice().sort((x, y) => y.time - x.time).slice(0, 500);
  if (!fills.length) fp.appendChild(empty('Chưa có lần khớp nào'));
  else fp.appendChild(table([
    { h: 'Thời gian', l: true, f: (r) => vt(r.time) },
    { h: 'Cặp', l: true, t: true, f: (r) => { const s = el('span'); s.appendChild(document.createTextNode(r.symbol)); if (r.bot) s.appendChild(el('span', 'badge test', 'bot')); return s; } },
    { h: 'Hướng', f: (r) => badge(r.side) },
    { h: 'Giá', f: (r) => px(r.price) }, { h: 'Số lượng', f: (r) => qty(r.qty) },
    { h: 'Đã chốt', m: true, f: (r) => pnl(r.realized) }, { h: 'Phí', f: (r) => pnl(r.fee) },
  ], fills));
}


// ---------- v2 paper test ----------
const ARM_COL = { signal: '#fcd535', committee: '#0ecb81' };
let v2 = null, tradeArm = 'committee';
function seriesData(pts) { // lightweight-charts needs strictly ascending unique times
  const m = new Map();
  (pts || []).forEach((p) => m.set(Math.round(p[0]) + TZ, p[1]));
  return Array.from(m).sort((a, b) => a[0] - b[0]).map((x) => ({ time: x[0], value: x[1] }));
}
function buildV2() {
  const root = $('#tab-v2');
  root.appendChild(el('div', 'banner', 'Hai bot ảo chạy bằng dữ liệu thật, tiền ảo 18,74 USDT mỗi bot: "Chỉ tín hiệu" và "Hội đồng AI". Cần ≥ 30 lệnh của bot Hội đồng AI để quyết định có chuyển sang tiền thật.'));
  const cols = el('div', 'cols'); cols.id = 'v2cols'; root.appendChild(cols);
  const cp = panel('Giá trị hai bot', 'Đường liền = tiền của từng bot sau mỗi lệnh đóng. Đường nét đứt = vốn ban đầu.');
  const box = el('div', 'chart'); cp.appendChild(box); root.appendChild(cp);
  const ch = mkChart(box, { localization: { priceFormatter: axisMoney } });
  const lines = {};
  Object.keys(ARM_COL).forEach((k) => { lines[k] = ch.addSeries(LC.LineSeries, { color: ARM_COL[k], lineWidth: 2, priceLineVisible: false, title: k === 'signal' ? 'Tín hiệu' : 'Hội đồng' }); });
  lines.base = ch.addSeries(LC.LineSeries, { color: C.mut, lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
  const pp = panel('Vị thế đang mở', 'Lệnh ảo đang giữ của cả hai bot.'); pp.appendChild(el('div')).id = 'v2open'; root.appendChild(pp);
  const tp = panel('Lệnh đã đóng', 'Mới nhất ở trên. R = lãi/lỗ chia cho số tiền rủi ro ban đầu.');
  const sel = el('select', 'sel'); sel.id = 'armSel';
  [['committee', 'Hội đồng AI'], ['signal', 'Chỉ tín hiệu']].forEach((a) => { const o = el('option', null, a[1]); o.value = a[0]; sel.appendChild(o); });
  sel.addEventListener('change', () => { tradeArm = sel.value; loadArmTrades().catch(() => {}); });
  tp.head.appendChild(sel); tp.appendChild(el('div')).id = 'v2trades'; root.appendChild(tp);
  charts.v2 = { ch, lines, box };
}
function armCol(a) {
  const c = el('div'), h = el('div', 'colh');
  const d = el('i', 'dot'); d.style.background = ARM_COL[a.name]; h.appendChild(d); h.appendChild(el('span', null, 'Bot "' + a.label_vi + '"'));
  c.appendChild(h);
  const g = el('div', 'grid');
  g.appendChild(card('Giá trị', money(a.equity, { unit: true, compact: true }), 'Vốn ' + money(a.start), 'Tiền ảo hiện có, gồm lãi/lỗ chưa chốt.'));
  g.appendChild(card('Lãi/lỗ', pnl(a.pnl, { unit: true, compact: true }), pctEl(a.pnl_pct), 'So với vốn ban đầu.'));
  g.appendChild(card('Số lệnh', String(a.trades), 'Đang mở ' + (a.open || []).length, 'Lệnh đã đóng.'));
  g.appendChild(card('Tỉ lệ thắng', pct(a.win_rate), a.wins + ' thắng', 'Lệnh có lãi ròng / tổng lệnh.'));
  g.appendChild(card('R trung bình', rEl(a.avg_r), null, 'Lãi/lỗ trung bình tính theo số tiền rủi ro mỗi lệnh.'));
  g.appendChild(card('Phí', money(a.fees, { unit: true }), null, 'Phí sàn ảo đã trừ.'));
  g.appendChild(card('Sụt giảm tối đa', pct(a.max_dd_pct), null, 'Mức tụt sâu nhất từ đỉnh.'));
  g.appendChild(card('Mức rủi ro hiện tại', pct(a.risk_pct, { d: 1 }) + ' / lệnh', null, '2% cho tới khi qua cổng lợi thế, sau đó 3%.'));
  c.appendChild(g);
  const eg = a.edge_gate || {}, n = eg.trades || 0, need = eg.trades_needed || 30;
  const gc = card('Cổng lợi thế', n + '/' + need + ' lệnh', 'R TB ' + rr(eg.avg_r) + (eg.passed ? ' · ĐÃ QUA' : ' · cần ≥ +0,10R'), 'Cần ≥ 30 lệnh và R trung bình ≥ +0.10 để tăng rủi ro lên 3%.');
  const pr = el('div', 'prog'), pi = el('i'); pi.style.width = Math.min(100, n / need * 100) + '%'; pr.appendChild(pi); gc.insertBefore(pr, gc.children[2]);
  gc.style.marginTop = '12px'; c.appendChild(gc);
  const ls = a.last_scan;
  const info = el('div', 'foot', ls ? 'Quét gần nhất: ' + vt(ls.time) + ' · ' + ls.setups + ' setup' + (ls.universe != null ? ' / ' + ls.universe + ' cặp' : '') : 'Chưa quét lần nào.');
  c.appendChild(info);
  if (a.name === 'committee') c.appendChild(el('div', 'foot', 'Chi phí AI: hôm nay ' + money(a.llm_today, { unit: true }) + ' · tổng ' + money(a.llm_total, { unit: true })));
  return c;
}
async function loadV2() {
  v2 = await api('/api/arms');
  const cols = $('#v2cols'); clear(cols);
  const arms = v2.arms || [];
  arms.forEach((a) => cols.appendChild(armCol(a)));
  const c = charts.v2;
  arms.forEach((a) => c.lines[a.name].setData(seriesData(a.curve)));
  const all = arms.reduce((x, a) => x.concat(a.curve || []), []);
  if (all.length) {
    const t = all.map((p) => p[0]), lo = Math.min.apply(null, t), hi = Math.max.apply(null, t.concat([Date.now() / 1000]));
    c.lines.base.setData(seriesData([[lo, arms[0].start], [hi, arms[0].start]]));
  }
  setTimeout(() => c.ch.timeScale().fitContent(), 150);
  const op = $('#v2open'); clear(op);
  const rows = [];
  arms.forEach((a) => (a.open || []).forEach((p) => rows.push(Object.assign({ arm: a.label_vi }, p))));
  if (!rows.length) op.appendChild(empty('Không có vị thế nào', 'Cả hai bot đang đứng ngoài thị trường.'));
  else op.appendChild(table([
    { h: 'Bot', l: true, f: (r) => r.arm }, { h: 'Cặp', l: true, t: true, f: (r) => short(r.symbol) }, { h: 'Hướng', m: true, f: (r) => badge(r.side) },
    { h: 'Khối lượng', f: (r) => qty(r.qty) }, { h: 'Giá vào', f: (r) => px(r.entry) },
    { h: 'Cắt lỗ (SL)', f: (r) => px(r.stop) }, { h: 'Chốt lời (TP)', f: (r) => px(r.tp) },
    { h: 'Giá hiện tại', f: (r) => num(r.mark) ? px(r.mark) : '-' },
  ], rows));
  await loadArmTrades();
}
async function loadArmTrades() {
  const arm = tradeArm, tr = await api('/api/arm_trades?arm=' + arm);
  if (arm !== tradeArm) return;
  const box = $('#v2trades'); clear(box);
  if (!tr.length) { box.appendChild(empty('Chưa có lệnh nào đã đóng')); return; }
  box.appendChild(table([
    { h: 'Đóng lúc', l: true, f: (t) => vt(t.close_time) }, { h: 'Cặp', l: true, t: true, f: (t) => short(t.symbol) },
    { h: 'Hướng', f: (t) => badge(t.side) }, { h: 'Khối lượng', f: (t) => qty(t.qty) },
    { h: 'Giá vào', f: (t) => px(t.entry) }, { h: 'Giá ra', f: (t) => px(t.exit) }, { h: 'Mở lúc', f: (t) => vt(t.open_time) },
    { h: 'Gộp', f: (t) => pnl(t.pnl) }, { h: 'Phí', f: (t) => pnl(-Math.abs(t.fees || 0)) },
    { h: 'Ròng', m: true, f: (t) => { const s = pnl(t.net); s.style.fontWeight = 600; return s; } },
    { h: 'R', f: (t) => rEl(t.r) }, { h: 'Lý do đóng', f: (t) => badge(t.why || '-') },
  ], tr));
}

// ---------- AI committee ----------
let debates = [], debFilter = 'all';
const OPEN = new Map(); // key -> user's choice; default: only the newest is open
const ANALYSTS = [['technical', 'Kỹ thuật'], ['derivatives', 'Dòng tiền phái sinh'], ['news', 'Tin tức & tâm lý']];
const STANCE = { long: 'MUA/LONG', short: 'BÁN/SHORT', neutral: 'TRUNG LẬP' };
function confBar(v) {
  const s = el('span'), c = el('span', 'conf'), i = el('i');
  i.style.width = Math.round(Math.min(1, Math.max(0, v || 0)) * 100) + '%'; c.appendChild(i); s.appendChild(c);
  s.appendChild(document.createTextNode(pct((v || 0) * 100, { d: 0 }))); return s;
}
function argBlock(title, a, kind) {
  const d = el('div', 'arg ' + kind); d.appendChild(el('h4', null, title));
  d.appendChild(document.createTextNode(a && a.argument ? a.argument : 'Không có dữ liệu.'));
  if (a && a.strongest_point) { const p = el('div', 'mut'); p.style.marginTop = '6px'; p.textContent = 'Điểm mạnh nhất: ' + a.strongest_point; d.appendChild(p); }
  return d;
}
function debateCard(d, idx) {
  const key = d.time + d.symbol, open = OPEN.has(key) ? OPEN.get(key) : idx === 0;
  const c = el('div', 'deb' + (open ? ' open' : ''));
  const h = el('div', 'dh');
  h.appendChild(el('span', 'mut', vt(d.time))); h.appendChild(el('b', null, short(d.symbol)));
  h.appendChild(badge(d.side || '-')); if (d.signal) h.appendChild(el('span', 'mut', d.signal));
  h.appendChild(el('span', 'sp'));
  h.appendChild(confBar(d.confidence));
  h.appendChild(el('span', 'mut', money(d.cost, { unit: true })));
  h.appendChild(d.action === 'open' ? el('span', 'badge enter', 'VÀO LỆNH') : el('span', 'badge skipd', 'BỎ QUA'));
  h.addEventListener('click', () => { OPEN.set(key, c.classList.toggle('open')); });
  c.appendChild(h);
  const b = el('div', 'db'), ag = el('div', 'ag');
  ANALYSTS.forEach((a) => {
    const m = el('div', 'mini'), v = (d.analysts || {})[a[0]];
    m.appendChild(el('h4', null, a[1]));
    if (!v || v.unavailable) m.appendChild(el('span', 'mut', 'Không có ý kiến' + (v && v.unavailable ? ' (' + v.unavailable + ')' : '')));
    else {
      const t = el('div'); t.appendChild(el('span', 'badge ' + (v.stance || 'neutral'), STANCE[v.stance] || v.stance));
      t.appendChild(document.createTextNode(' ')); t.appendChild(confBar(v.confidence)); m.appendChild(t);
      const ul = el('ul'); (v.key_points || []).forEach((p) => ul.appendChild(el('li', null, p))); m.appendChild(ul);
    }
    ag.appendChild(m);
  });
  b.appendChild(ag);
  b.appendChild(argBlock('Phe mua (Bull)', d.bull, 'bull')); b.appendChild(argBlock('Phe bán (Bear)', d.bear, 'bear'));
  const lead = el('div', 'arg'); lead.appendChild(el('h4', null, 'Lead chốt'));
  lead.appendChild(document.createTextNode(d.rationale || '-'));
  const m = el('div', 'mut'); m.style.marginTop = '6px';
  m.textContent = 'SL ' + fnum(d.sl_atr, 2) + '×ATR · TP ' + fnum(d.tp_r, 2) + 'R'; lead.appendChild(m);
  b.appendChild(lead); c.appendChild(b);
  return c;
}
function renderDebates() {
  const root = $('#tab-committee'); clear(root);
  const p = panel('Hội đồng AI', '3 chuyên gia phân tích, phe mua và phe bán tranh luận, rồi Lead chốt vào lệnh hay bỏ qua. Bấm vào dòng để xem chi tiết.');
  const chips = el('div', 'chips');
  [['all', 'Tất cả'], ['open', 'Vào lệnh'], ['skip', 'Bỏ qua']].forEach((x) => {
    const b = el('button', 'chip' + (debFilter === x[0] ? ' on' : ''), x[1]); b.type = 'button';
    b.addEventListener('click', () => { debFilter = x[0]; renderDebates(); });
    chips.appendChild(b);
  });
  p.head.appendChild(chips); root.appendChild(p);
  const rows = debates.filter((d) => debFilter === 'all' || d.action === debFilter);
  if (!rows.length) { p.appendChild(empty('Chưa có cuộc tranh luận nào — hội đồng chỉ họp khi bot tìm thấy setup.')); return; }
  rows.forEach((d, i) => root.appendChild(debateCard(d, i)));
}
async function loadDebates() { debates = await api('/api/debates?limit=50'); renderDebates(); }

// ---------- Hệ thống (system report) ----------
let sysLoaded = false;
async function loadSystem() {
  if (sysLoaded) return;
  const r = await fetch('/static/report.html', { credentials: 'same-origin', redirect: 'manual' });
  if (r.type === 'opaqueredirect') { window.location = '/login'; throw new Error('auth'); }
  if (!r.ok) throw new Error('report ' + r.status);
  const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
  const root = $('#tab-system');
  // first-party static file (not user data): its scoped <style data-rpt> and .rpt wrapper are imported as-is
  doc.querySelectorAll('style[data-rpt]').forEach((st) => root.appendChild(document.importNode(st, true)));
  const rpt = doc.querySelector('.rpt');
  if (!rpt) throw new Error('report markup');
  root.appendChild(document.importNode(rpt, true));
  root.querySelectorAll('a[href]').forEach((a) => { if (!a.getAttribute('href').startsWith('#')) { a.target = '_blank'; a.rel = 'noopener'; } });
  root.addEventListener('click', (ev) => { // in-page anchors scroll inside the tab and never touch the dashboard hash route
    const a = ev.target.closest && ev.target.closest('a[href^="#"]');
    if (!a) return;
    ev.preventDefault();
    const t = root.querySelector('[id="' + a.getAttribute('href').slice(1).replace(/"/g, '') + '"]');
    if (t) t.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  });
  sysLoaded = true;
}

// ---------- VND rate ----------
function renderFx() {
  const b = $('#fx');
  if (!fx) { b.textContent = 'Tỉ giá USDT/VND: chưa lấy được, đang hiển thị USDT.'; return; }
  b.textContent = '1 USDT = ' + nf(0, 0).format(fx.usdt_vnd) + ' ₫ · ' + fx.source + ' · cập nhật ' + new Date((fx.time + TZ) * 1000).toISOString().slice(11, 16) + (fx.stale ? ' (cũ)' : '');
}
async function loadFx() {
  try { fx = await api('/api/fx'); } catch (e) { if (e.message === 'auth') return; }
  renderFx();
  if (unit === 'vnd') refreshView();
}
function refreshView() { // re-render everything that shows money
  if (liveData) renderPositions();
  loaders[currentTab()]().catch(() => {});
}
function setUnit(u) {
  unit = u; localStorage.setItem('unit', u);
  document.querySelectorAll('#unit button').forEach((b) => b.classList.toggle('on', b.dataset.u === u));
  refreshView();
}
document.querySelectorAll('#unit button').forEach((b) => b.addEventListener('click', () => setUnit(b.dataset.u)));
document.querySelectorAll('#unit button').forEach((b) => b.classList.toggle('on', b.dataset.u === unit));

// ---------- phone navigation: bottom bar + "Thêm" sheet ----------
const NS = 'http://www.w3.org/2000/svg';
const ICON = {
  overview: 'M4 4h7v7H4z M13 4h7v4h-7z M13 11h7v9h-7z M4 14h7v6H4z',
  positions: 'M12 3l9 5-9 5-9-5z M3 13l9 5 9-5',
  history: 'M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0-18z M12 7v5l3 2',
  v2: 'M9 3h6 M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3',
  more: 'M5 12h.01 M12 12h.01 M19 12h.01',
  decisions: 'M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z',
  account: 'M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M3 7l2-3h12 M16 14h2',
  committee: 'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M3 20c0-3 3-5 6-5s6 2 6 5 M17 11a3 3 0 1 0 0-6 M21 20c0-2-1-4-3-5',
  system: 'M6 3h9l4 4v14H6z M14 3v5h5 M9 13h7 M9 17h7',
  logout: 'M10 4H5v16h5 M15 8l4 4-4 4 M19 12H9',
};
function icon(name, size) {
  const s = document.createElementNS(NS, 'svg');
  [['viewBox', '0 0 24 24'], ['width', size], ['height', size], ['fill', 'none'], ['stroke', 'currentColor'], ['stroke-width', name === 'more' ? 3 : 2], ['stroke-linecap', 'round'], ['stroke-linejoin', 'round'], ['aria-hidden', 'true']].forEach((x) => s.setAttribute(x[0], x[1]));
  ICON[name].split(' M').forEach((d, i) => { const p = document.createElementNS(NS, 'path'); p.setAttribute('d', (i ? 'M' : '') + d); s.appendChild(p); });
  return s;
}
const MAIN_NAV = [['overview', 'Tổng quan'], ['positions', 'Vị thế'], ['history', 'Lịch sử'], ['v2', 'Thử nghiệm']];
const MORE_NAV = [['decisions', 'Quyết định AI'], ['account', 'Tài khoản'], ['committee', 'Hội đồng AI'], ['system', 'Hệ thống']];
function buildNav() {
  const nav = $('#bnav'), sheet = $('#sheet');
  MAIN_NAV.forEach((t) => {
    const a = el('a'); a.href = '#' + t[0]; a.dataset.tab = t[0];
    a.appendChild(icon(t[0], 22)); a.appendChild(el('span', null, t[1]));
    if (t[0] === 'positions') { const c = el('b', 'cnt posCount'); c.hidden = true; a.appendChild(c); }
    nav.appendChild(a);
  });
  const more = el('button'); more.type = 'button'; more.id = 'moreBtn'; more.setAttribute('aria-haspopup', 'dialog'); more.setAttribute('aria-expanded', 'false');
  more.appendChild(icon('more', 22)); more.appendChild(el('span', null, 'Thêm')); nav.appendChild(more);
  const sp = el('div', 'sp'); sp.setAttribute('role', 'dialog'); sp.setAttribute('aria-label', 'Thêm');
  sp.appendChild(el('div', 'gr'));
  MORE_NAV.forEach((t) => { const a = el('a'); a.href = '#' + t[0]; a.dataset.tab = t[0]; a.appendChild(icon(t[0], 24)); a.appendChild(el('span', null, t[1])); sp.appendChild(a); });
  const f = el('form'); f.method = 'post'; f.action = '/logout';
  const lb = el('button'); lb.type = 'submit'; lb.appendChild(icon('logout', 24)); lb.appendChild(el('span', null, 'Đăng xuất')); f.appendChild(lb); sp.appendChild(f);
  sheet.appendChild(sp);
  const open = (v) => { sheet.hidden = !v; more.setAttribute('aria-expanded', String(v)); if (v) sp.querySelector('a').focus(); else more.focus(); };
  more.addEventListener('click', () => open(sheet.hidden));
  sheet.addEventListener('click', (ev) => { if (ev.target === sheet || ev.target.closest('a')) sheet.hidden = true, more.setAttribute('aria-expanded', 'false'); });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !sheet.hidden) open(false); });
}

// ---------- routing ----------
const TABS = ['overview', 'positions', 'history', 'decisions', 'account', 'v2', 'committee', 'system'];
const loaders = { overview: loadOverview, positions: loadCandles, history: loadHistory, decisions: loadDecisions, account: loadAccount, v2: loadV2, committee: loadDebates, system: loadSystem };
function currentTab() { const h = location.hash.slice(1); return TABS.includes(h) ? h : 'overview'; }
function route() {
  const t = currentTab();
  TABS.forEach((n) => { $('#tab-' + n).classList.toggle('on', n === t); });
  document.querySelectorAll('#tabs a, #bnav a, #sheet a').forEach((a) => a.classList.toggle('on', a.dataset.tab === t));
  $('#moreBtn').classList.toggle('on', MORE_NAV.some((x) => x[0] === t));
  const on = document.querySelector('#tabs a.on');   // desktop nav may scroll sideways: keep the open tab visible
  if (on) requestAnimationFrame(() => on.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
  loaders[t]().catch((e) => { if (e.message !== 'auth') console.error(e); });
}
window.addEventListener('hashchange', () => { window.scrollTo(0, 0); route(); });

buildOverview(); buildPositions(); buildV2(); buildNav();
route();
loadFx();
setInterval(loadFx, 600000);
pollLive();
setInterval(pollLive, 5000);
setInterval(() => { if (currentTab() === 'positions') loadCandles().catch(() => {}); }, 30000);
setInterval(() => { if (currentTab() === 'overview') loadOverview().catch(() => {}); }, 30000);
setInterval(() => { if (currentTab() === 'v2') loadV2().catch(() => {}); }, 15000);
setInterval(() => { if (currentTab() === 'committee') loadDebates().catch(() => {}); }, 30000);

// TradingView attribution (license)
const f = el('div', 'foot'); f.appendChild(document.createTextNode('Biểu đồ bởi '));
const a = el('a', null, 'TradingView Lightweight Charts'); a.href = 'https://www.tradingview.com/'; a.target = '_blank'; a.rel = 'noopener';
f.appendChild(a); document.querySelector('main').appendChild(f);
})();
