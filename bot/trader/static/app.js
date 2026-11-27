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
function f2(v, d) { return num(v) ? v.toFixed(d == null ? 2 : d) : '-'; }
function sg(v, d) { return num(v) ? (v > 0 ? '+' : '') + v.toFixed(d == null ? 2 : d) : '-'; }
function cls(v) { return !num(v) || v === 0 ? '' : v > 0 ? 'up' : 'dn'; }
function pn(v, d, suffix) { return el('span', cls(v), sg(v, d) + (suffix || '')); }
function vt(t) { // "11-27 14:00"
  if (!num(t)) return '-';
  return new Date((t + TZ) * 1000).toISOString().slice(5, 16).replace('T', ' ');
}
function pdec(p) { return !num(p) ? 2 : p >= 1000 ? 2 : p >= 10 ? 3 : p >= 1 ? 4 : 5; }
function px(v) { return f2(v, pdec(v)); }
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
// cols: [{h, f(row)->string|Node, l:true for left align, k: sort key fn}]
function table(cols, rows, opt) {
  opt = opt || {};
  const wrap = el('div', 'tw'), t = el('table'), thead = el('thead'), tr = el('tr');
  cols.forEach((c) => {
    const th = el('th', (c.l ? 'l ' : '') + (c.k ? 'sort' : ''), c.h);
    if (c.k && opt.onSort) th.addEventListener('click', () => opt.onSort(c));
    tr.appendChild(th);
  });
  thead.appendChild(tr); t.appendChild(thead);
  const tb = el('tbody');
  rows.forEach((r) => {
    const row = el('tr');
    cols.forEach((c) => {
      const td = el('td', c.cls || (c.l ? 'l' : ''));
      const v = c.f(r);
      if (v instanceof Node) td.appendChild(v); else td.textContent = v == null ? '-' : v;
      if (opt.flash) opt.flash(r, c, td);
      row.appendChild(td);
    });
    tb.appendChild(row);
  });
  t.appendChild(tb);
  if (opt.foot) { const tf = el('tfoot'), fr = el('tr'); opt.foot.forEach((x) => { const td = el('td'); if (x instanceof Node) td.appendChild(x); else td.textContent = x; fr.appendChild(td); }); tf.appendChild(fr); t.appendChild(tf); }
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
  s.textContent = 'TRỰC TIẾP · cập nhật ' + (age < 90 ? age + ' giây' : Math.round(age / 60) + ' phút') + ' trước';
  b.classList.toggle('stale', age > 30);
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
  const ch1 = mkChart(b1, { localization: { priceFormatter: (p) => p.toFixed(2) } });
  const eq = ch1.addSeries(LC.BaselineSeries, {
    baseValue: { type: 'price', price: 0 },
    topLineColor: C.up, topFillColor1: 'rgba(14,203,129,.28)', topFillColor2: 'rgba(14,203,129,.02)',
    bottomLineColor: C.dn, bottomFillColor1: 'rgba(246,70,93,.02)', bottomFillColor2: 'rgba(246,70,93,.28)',
    lineWidth: 2, priceLineVisible: false,
  });
  const ch2 = mkChart(b2, { timeScale: { borderColor: C.line, timeVisible: false } });
  const bars = ch2.addSeries(LC.HistogramSeries, { priceLineVisible: false, lastValueVisible: false });
  const cum = ch2.addSeries(LC.LineSeries, { color: C.acc, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
  charts.overview = { ch1, eq, ch2, bars, cum, b1, b2, p1, p2 };
}
async function loadOverview() {
  const [s, e] = await Promise.all([api('/api/summary'), api('/api/equity')]);
  const k = $('#kpis'); clear(k);
  const st = s.start || {}, nw = s.now || {}, ss = s.stats || {};
  k.appendChild(card('Vốn ban đầu', f2(st.capital) + ' USDT', 'Futures ' + f2(st.futures) + ' + credit AI ' + f2(st.llm_credit), 'Số tiền bot bắt đầu chạy, gồm tiền giao dịch và tiền trả cho AI.'));
  k.appendChild(card('Giá trị hiện tại', f2(nw.value) + ' USDT', 'Futures ' + f2(nw.futures_value) + ' + AI còn ' + f2(nw.llm_remaining), 'Tổng tiền bot đang có bây giờ.'));
  k.appendChild(card('Lãi/lỗ ròng', pn(nw.pnl, 2, ' USDT'), pn(nw.pnl_pct, 2, '%'), 'Hiện tại so với vốn ban đầu. Xanh là lãi, đỏ là lỗ.'));
  k.appendChild(card('Lãi/lỗ hôm nay', pn(nw.today_pnl, 2, ' USDT'), null, 'Kết quả riêng của hôm nay.'));
  k.appendChild(card('Tỉ lệ thắng', f2(ss.win_rate, 1) + '%', (ss.wins || 0) + ' thắng / ' + (ss.trades || 0) + ' lệnh', 'Trong 100 lệnh đã đóng, có bao nhiêu lệnh có lãi.'));
  k.appendChild(card('Chi phí AI', f2(ss.llm_spent, 4) + ' USDT', 'Còn lại ' + f2(nw.llm_remaining) + ' credit', 'Tiền đã trả để AI phân tích thị trường.'));
  k.appendChild(card('Phí + funding', pn((ss.fees || 0) + (ss.funding || 0), 4, ' USDT'), 'Phí ' + sg(ss.fees, 4) + ' / funding ' + sg(ss.funding, 4), 'Phí sàn mỗi lệnh và phí giữ vị thế qua đêm.'));
  k.appendChild(card('Sụt giảm tối đa', f2(ss.max_dd_pct, 2) + '%', 'Đã chốt ' + sg(ss.realized, 4) + ' USDT', 'Mức tụt sâu nhất từ đỉnh. Càng nhỏ càng an toàn.'));
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
  candleChart = mkChart(box);
  candleSeries = candleChart.addSeries(LC.CandlestickSeries, { upColor: C.up, downColor: C.dn, borderUpColor: C.up, borderDownColor: C.dn, wickUpColor: C.up, wickDownColor: C.dn });
  markerApi = LC.createSeriesMarkers(candleSeries, []);
}
function renderPositions() {
  const L = liveData; if (!L) return;
  const body = $('#posBody'), pos = L.positions || [];
  const cnt = $('#posCount'); cnt.hidden = !pos.length; cnt.textContent = pos.length;
  $('#eqLine').textContent = 'Tổng tài sản ' + f2(L.equity) + ' · Ví ' + f2(L.wallet) + ' · Lãi/lỗ chưa chốt ' + sg(L.upnl);
  clear(body);
  if (!pos.length) { body.appendChild(empty('Không có vị thế nào', 'Bot đang đứng ngoài thị trường.')); return; }
  const cur = {};
  const cols = [
    { h: 'Cặp', l: true, f: (r) => short(r.symbol) },
    { h: 'Hướng', f: (r) => badge(r.side) },
    { h: 'Khối lượng', f: (r) => f2(r.qty, 4) },
    { h: 'Giá vào', f: (r) => px(r.entry) },
    { h: 'Giá hiện tại', key: 'mark', f: (r) => px(r.mark) },
    { h: 'Giá thanh lý', f: (r) => px(r.liq) },
    { h: 'Lãi/lỗ chưa chốt (ROE)', key: 'upnl', f: (r) => { const s = el('span', cls(r.upnl)); s.textContent = sg(r.upnl, 4) + ' (' + sg(r.roe_pct, 2) + '%)'; return s; } },
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
  const pr = pdec(last);
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
  g.appendChild(card('Lãi/lỗ gộp', pn(sum('pnl'), 4), null, 'Trước khi trừ phí.'));
  g.appendChild(card('Phí', pn(sum('fees'), 4), null, 'Phí sàn đã trả.'));
  g.appendChild(card('Funding', pn(sum('funding'), 4), null, 'Phí giữ vị thế qua đêm.'));
  g.appendChild(card('Lãi/lỗ ròng', pn(sum('net'), 4, ' USDT'), null, 'Kết quả thật sau mọi chi phí.'));
  root.appendChild(g);
  const p = panel('Lịch sử lệnh', 'Các lệnh bot đã đóng, mới nhất ở trên. "Ròng" = lãi/lỗ sau khi trừ phí.');
  p.appendChild(table([
    { h: 'Đóng lúc', l: true, f: (t) => vt(t.close_time) },
    { h: 'Cặp', l: true, f: (t) => { const s = el('span'); s.appendChild(document.createTextNode(short(t.symbol))); if (t.test) s.appendChild(el('span', 'badge test', 'thử')); return s; } },
    { h: 'Hướng', f: (t) => badge(t.side) },
    { h: 'Khối lượng', f: (t) => f2(t.qty, 4) },
    { h: 'Giá vào', f: (t) => px(t.entry) },
    { h: 'Giá ra', f: (t) => px(t.exit) },
    { h: 'Mở lúc', f: (t) => vt(t.open_time) },
    { h: 'Gộp', f: (t) => pn(t.pnl, 4) },
    { h: 'Phí', f: (t) => pn(t.fees, 4) },
    { h: 'Funding', f: (t) => pn(t.funding, 4) },
    { h: 'Ròng', f: (t) => { const s = pn(t.net, 4); s.style.fontWeight = 600; return s; } },
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
    { h: 'Cặp', l: true, f: (d) => short(d.symbol) },
    { h: 'Hành động', f: (d) => badge(d.action) },
    { h: 'Độ tự tin', f: (d) => { const s = el('span'); const c = el('span', 'conf'), i = el('i'); i.style.width = Math.round(Math.min(1, Math.max(0, d.confidence || 0)) * 100) + '%'; c.appendChild(i); s.appendChild(c); s.appendChild(document.createTextNode(f2((d.confidence || 0) * 100, 0) + '%')); return s; } },
    { h: 'Kết quả', f: (d) => d.accepted ? el('span', 'up', '✓') : el('span', 'dn', d.reject || 'bị từ chối') },
    { h: 'Cắt lỗ (SL)', f: (d) => num(d.sl) ? px(d.sl) : '-' },
    { h: 'Chốt lời (TP)', f: (d) => num(d.tp) ? px(d.tp) : '-' },
    { h: 'Lý do của AI', cls: 'wrap', f: (d) => d.reason || '-' },
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
  root.appendChild(el('div', 'foot', 'Dữ liệu từ ' + vt(cv.from) + ' đến ' + vt(cv.to) + ' · nguồn: ' + ((cv.sources || []).join(', ') || '-')));
  const t = a.totals || {}, g = el('div', 'grid');
  g.appendChild(card('Tiền nạp / chuyển vào', f2(t.transfer_in) + ' USDT', null, 'Tiền bạn đưa vào tài khoản futures.'));
  g.appendChild(card('Tiền rút / chuyển ra', f2(t.transfer_out) + ' USDT', null, 'Tiền bạn lấy ra khỏi futures.'));
  g.appendChild(card('Lãi/lỗ đã chốt', pn(t.realized, 2), null, 'Lãi/lỗ của các lệnh đã đóng.'));
  g.appendChild(card('Phí', pn(t.fees, 2), null, 'Phí giao dịch đã trả.'));
  g.appendChild(card('Funding', pn(t.funding, 2), null, 'Phí giữ vị thế qua đêm.'));
  g.appendChild(card('Kết quả giao dịch ròng', pn(t.net, 2, ' USDT'), null, 'Đã chốt trừ phí và funding.'));
  root.appendChild(g);
  const mp = panel('Kết quả theo tháng', 'Cột = kết quả ròng từng tháng, đường vàng = cộng dồn.');
  const mb = el('div', 'chart sm'); mp.appendChild(mb); root.appendChild(mp);
  const mon = a.monthly || [];
  if (!mon.length) { mb.remove(); mp.appendChild(empty('Chưa có dữ liệu theo tháng')); }
  else {
    const mc = mkChart(mb, { timeScale: { borderColor: C.line, timeVisible: false, tickMarkFormatter: monthFmt }, localization: { timeFormatter: monthFmt } });
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
      col('Đã chốt', 'realized', (r) => pn(r.realized, 2)), col('Phí', 'fees', (r) => pn(r.fees, 2)),
      col('Funding', 'funding', (r) => pn(r.funding, 2)), col('Ròng', 'net', (r) => pn(r.net, 2)), col('Số khớp', 'fills', (r) => String(r.fills)),
    ], syms, { onSort: (c) => { symSort = { k: c.k, dir: symSort.k === c.k ? -symSort.dir : -1 }; renderAccount(); } }));
  }
  const fp = panel('Các lần khớp lệnh gần nhất', 'Tối đa 500 lần khớp. Nhãn "bot" = do bot đặt.'); root.appendChild(fp);
  const fills = (a.fills || []).slice().sort((x, y) => y.time - x.time).slice(0, 500);
  if (!fills.length) fp.appendChild(empty('Chưa có lần khớp nào'));
  else fp.appendChild(table([
    { h: 'Thời gian', l: true, f: (r) => vt(r.time) },
    { h: 'Cặp', l: true, f: (r) => { const s = el('span'); s.appendChild(document.createTextNode(r.symbol)); if (r.bot) s.appendChild(el('span', 'badge test', 'bot')); return s; } },
    { h: 'Hướng', f: (r) => badge(r.side) },
    { h: 'Giá', f: (r) => px(r.price) }, { h: 'Số lượng', f: (r) => f2(r.qty, 4) },
    { h: 'Đã chốt', f: (r) => pn(r.realized, 4) }, { h: 'Phí', f: (r) => pn(r.fee, 4) },
  ], fills));
}

// ---------- routing ----------
const TABS = ['overview', 'positions', 'history', 'decisions', 'account'];
const loaders = { overview: loadOverview, positions: loadCandles, history: loadHistory, decisions: loadDecisions, account: loadAccount };
function currentTab() { const h = location.hash.slice(1); return TABS.includes(h) ? h : 'overview'; }
function route() {
  const t = currentTab();
  TABS.forEach((n) => { $('#tab-' + n).classList.toggle('on', n === t); });
  document.querySelectorAll('#tabs a').forEach((a) => a.classList.toggle('on', a.dataset.tab === t));
  loaders[t]().catch((e) => { if (e.message !== 'auth') console.error(e); });
}
window.addEventListener('hashchange', route);

buildOverview(); buildPositions();
route();
pollLive();
setInterval(pollLive, 5000);
setInterval(() => { if (currentTab() === 'positions') loadCandles().catch(() => {}); }, 30000);
setInterval(() => { if (currentTab() === 'overview') loadOverview().catch(() => {}); }, 30000);

// TradingView attribution (license)
const f = el('div', 'foot'); f.appendChild(document.createTextNode('Biểu đồ bởi '));
const a = el('a', null, 'TradingView Lightweight Charts'); a.href = 'https://www.tradingview.com/'; a.target = '_blank'; a.rel = 'noopener';
f.appendChild(a); document.querySelector('main').appendChild(f);
})();
