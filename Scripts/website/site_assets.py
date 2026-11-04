"""
The website's page, style and behaviour (kept here as text because the scripts/
folder only holds .py files). build_website.py writes them out as
Data/website/index.html, style.css and app.js. Edit here, then rebuild.

The site is plain HTML + CSS + JavaScript: no server, no internet needed.
Open Data/website/index.html by double-clicking it, or upload the whole
Data/website/ folder to any static host (GitHub Pages, Netlify, college server).
"""

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RealScope</title>
<meta name="description" content="Microscope slides for first-year biology: zoom into each diagram, compare it with a real photo, and learn the common slide mistakes.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Atkinson+Hyperlegible:wght@400;700&display=swap">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top">
  <div class="wrap top-in">
    <a class="brand" href="#specimens" aria-label="RealScope home">
      <svg width="30" height="30" viewBox="0 0 32 32" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 3h10v5H11z"/><path d="M12 8l-1 9h10l-1-9"/><circle cx="16" cy="24" r="5"/><circle cx="16" cy="24" r="1.8" fill="#FFC857" stroke="none"/></svg>
      <span>RealScope</span>
    </a>
    <span class="tagline">See it the way it really looks under the microscope.</span>
    <nav class="nav" aria-label="Main">
      <a href="#specimens" data-tab="specimens">Specimens</a>
      <a href="#viewer" data-tab="viewer">Slide viewer</a>
      <a href="#mistakes" data-tab="mistakes">Mistakes</a>
      <a href="#manual" data-tab="manual">Lab manual</a>
    </nav>
  </div>
</header>
<div id="view" class="view"></div>
<footer class="foot">
  <div class="wrap foot-in">
    <span>Diagrams are reproduced from the lab manual; every specimen gives its page number.</span>
    <a href="#manual">Read the lab manual &rarr;</a>
  </div>
</footer>
<script src="site_data.js"></script>
<script src="app.js"></script>
</body>
</html>
"""

STYLE_CSS = r""":root{
  --ink:#13212B; --muted:#4A5A63; --line:#D5DEE2; --bg:#F4F6F8; --card:#FFFFFF;
  --brand:#0E3A46; --brand-soft:#DDF1EE; --gold:#FFC857; --blue:#1E5FA8; --blue-soft:#E3EEFB;
  --warm:#FFE8DA; --warm-ink:#6A2A06;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 'Atkinson Hyperlegible',system-ui,sans-serif}
h1,h2{font-family:'Bricolage Grotesque',sans-serif;letter-spacing:-.02em;margin:0}
a{color:var(--blue)}
button{font:inherit;color:inherit}
button,a,.chip,.tile,.card{transition:background-color .18s ease,color .18s ease,border-color .18s ease,transform .15s ease,box-shadow .18s ease}
button:active,.card:active{transform:scale(.98)}
:focus-visible{outline:3px solid var(--gold);outline-offset:2px}
.wrap{max-width:1280px;margin:0 auto;padding:0 clamp(16px,4vw,32px)}
.sr{position:absolute;left:-9999px}

/* header / footer */
.top{background:var(--brand);color:#fff;position:sticky;top:0;z-index:20}
@media (max-width:700px){.top{position:static}}
.top-in{display:flex;flex-wrap:wrap;align-items:center;gap:6px 20px;padding-top:8px;padding-bottom:8px}
.brand{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none;min-height:44px}
.brand span{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:22px}
.tagline{flex:1 1 240px;font-size:14px;color:#BFE3E0}
.nav{display:flex;flex-wrap:wrap;gap:4px}
.nav a{min-height:40px;display:inline-flex;align-items:center;padding:0 14px;border-radius:10px;color:#fff;text-decoration:none;font-weight:700}
.nav a:hover{background:rgba(255,255,255,.12)}
.nav a[aria-current=page]{background:var(--gold);color:var(--brand)}
.foot{background:var(--brand);color:#BFE3E0;margin-top:24px}
.foot-in{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 20px;padding-top:18px;padding-bottom:18px;font-size:13px}
.foot a{color:#fff;font-weight:700}

/* page transitions */
.view{min-height:70vh}
.view.enter{animation:rsIn .3s ease-out both}
@keyframes rsIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes rsSpin{to{transform:rotate(360deg)}}
.fade{opacity:0;transition:opacity .25s ease}
.fade.ok{opacity:1}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}

/* shared bits */
.band{border-bottom:1px solid rgba(0,0,0,.06)}
.band-in{padding-top:clamp(18px,4vw,32px);padding-bottom:clamp(18px,4vw,32px)}
.h1{font-weight:800;font-size:clamp(28px,6vw,46px);line-height:1.05}
.lead{margin:8px 0 0;font-size:16px;max-width:760px}
.pill{display:inline-block;font-size:11px;font-weight:700;border-radius:999px;padding:2px 8px}
.chips{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;scrollbar-width:thin}
.chip{flex:none;min-height:40px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:#fff;font-size:14px;font-weight:700;cursor:pointer;white-space:nowrap}
.chip[aria-pressed=true],.chip[aria-current=true]{background:var(--ink);border-color:var(--ink);color:#fff}
.btn{min-height:44px;padding:0 14px;border-radius:10px;border:1px solid #C9D3D8;background:#fff;font-weight:700;cursor:pointer}
.btn:hover{border-color:var(--ink)}
.icon-btn{width:42px;height:42px;border-radius:10px;border:1px solid #C9D3D8;background:#fff;cursor:pointer;font-size:21px;font-weight:700;line-height:1}
.box{background:var(--card);border:1px solid var(--line);border-radius:16px}
.main{padding-top:20px;padding-bottom:40px;display:flex;flex-direction:column;gap:16px}

/* specimens */
.hero{background:var(--brand-soft)}
.hero-in{display:flex;flex-wrap:wrap;gap:20px 36px;align-items:center}
.hero-l{flex:1 1 320px;min-width:0;display:flex;flex-direction:column;gap:12px}
.hero-l .h1{color:var(--brand)}
.hero-r{flex:1 1 460px;min-width:0}
.search{max-width:420px;display:flex;align-items:center;gap:8px;background:#fff;border:2px solid var(--brand);border-radius:12px;padding:0 6px 0 12px;min-height:48px}
.search input{flex:1;min-width:0;border:0;font:inherit;font-size:16px;min-height:44px;background:transparent;outline:none}
.search button{border:0;background:#E6EEF0;border-radius:999px;width:36px;height:36px;cursor:pointer}
.kicker{margin:0 0 8px;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#2A4A52}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,140px),1fr));gap:10px}
.tile{display:flex;flex-direction:column;gap:10px;padding:12px;min-height:76px;border-radius:12px;border:2px solid transparent;background:#fff;cursor:pointer;text-align:left}
.tile:hover{transform:translateY(-2px);box-shadow:0 4px 14px rgba(0,0,0,.08)}
.tile .row{display:flex;justify-content:space-between;align-items:center}
.tile .dot{width:14px;height:14px;border-radius:4px}
.tile b{font-size:15px;line-height:1.2}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,165px),1fr));gap:14px}
.card{display:flex;flex-direction:column;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;text-decoration:none;color:var(--ink)}
.card:hover{transform:translateY(-3px);box-shadow:0 6px 18px rgba(0,0,0,.09)}
.card .th2{display:grid;grid-template-columns:1fr;height:140px;border-bottom:1px solid var(--line)}
.card .half{position:relative;display:flex;align-items:center;justify-content:center;padding:8px;min-width:0;overflow:hidden}
.card .half img{max-width:100%;max-height:100%;object-fit:contain}
.card .half.ph{background:#1B1F22;padding:0}
.card .half img.cover{width:100%;height:100%;max-width:none;max-height:none;object-fit:cover}
.card .none{font-size:11px;font-weight:700;color:#C9B48A;text-align:center;line-height:1.3}
.card .tag{position:absolute;left:4px;bottom:4px;font-size:10px;font-weight:700;padding:1px 6px;border-radius:999px;background:rgba(255,255,255,.88);color:#13212B}
.card .bd{padding:10px 12px 12px;display:flex;flex-direction:column;gap:6px;flex:1}
.card .nm{font-weight:700;line-height:1.25;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.5em}
.empty{background:#fff;border:1px dashed #B9C4C9;border-radius:14px;padding:28px;text-align:center}

/* viewer */
.vbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.vbar select{flex:1 1 220px;min-width:0;max-width:420px;min-height:44px;padding:0 10px;border-radius:10px;border:1px solid #C9D3D8;background:#fff;font:inherit;font-size:15px}
.vhead{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px 20px}
.vhead .meta{margin:0 0 4px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:13px;color:var(--muted)}
.vhead h1{font-weight:800;font-size:clamp(26px,5vw,40px);line-height:1.1}
.vhead .desc{margin:8px 0 0;max-width:760px;font-size:16px;color:#2E3E46}
.seg{display:inline-flex;flex-wrap:wrap;background:#fff;border:1px solid var(--line);border-radius:12px;padding:3px}
.seg button{min-height:40px;padding:0 14px;border:0;border-radius:9px;background:transparent;font-weight:700;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--brand);color:#fff}
.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:16px;align-items:start}
.panel{overflow:hidden}
.pbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px 8px 14px}
.pbar .ttl{display:inline-flex;align-items:center;gap:12px;flex-wrap:wrap;font-weight:700}
.toggle{display:inline-flex;align-items:center;gap:6px;min-height:40px;padding:0 10px;border-radius:999px;background:#fff;border:1px solid #A9C2E6;font-size:14px;font-weight:700;color:#123F73;cursor:pointer}
.toggle input{width:18px;height:18px;margin:0;accent-color:var(--blue)}
.zoom{display:inline-flex;align-items:center;gap:4px}
.zoom .pct{min-width:52px;text-align:center;font-size:14px;font-weight:700;font-variant-numeric:tabular-nums}
.vp{position:relative;overflow:hidden;height:clamp(260px,52vw,520px);touch-action:pan-y;cursor:zoom-in;user-select:none}
.vp.zoomed{touch-action:none;cursor:grab}
.vp.drag{cursor:grabbing}
.vp .inner{position:absolute;inset:12px;transform-origin:50% 50%;transition:transform .18s ease-out}
.vp.drag .inner{transition:none}
.vp img{display:block;width:100%;height:100%;object-fit:contain;pointer-events:none;-webkit-user-drag:none}
.vp.missing{display:flex;align-items:center;justify-content:center;background:#FFFBF2;cursor:default}
.miss{display:flex;flex-direction:column;align-items:center;gap:8px;text-align:center;padding:20px;max-width:420px}
.miss .t{margin:0;font-weight:700}.miss .s{margin:0;font-size:14px;color:#4A5A63;overflow-wrap:anywhere}
.hint{margin:0;padding:8px 14px;font-size:13px;color:var(--muted);border-top:1px solid #E6ECEE}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px;align-items:start}
.sec{padding:16px}
.sec h2{font-size:20px;font-weight:800;margin-bottom:10px}
.labels{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}
.labels li{font-size:14px;font-weight:700;padding:6px 12px;border-radius:999px}
.src{display:flex;gap:12px;align-items:flex-start;margin-top:10px}
.src .ic{flex:none;width:36px;height:36px;border-radius:10px;display:grid;place-items:center}
.src p{margin:0}
.src .t{font-weight:700}
.src .s{font-size:14px;color:#2E3E46}
.linkbtn{background:none;border:0;padding:0;min-height:36px;cursor:pointer;font-weight:700;text-decoration:underline}
.sibs{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}
.sib{flex:none;width:132px;display:flex;flex-direction:column;gap:6px;padding:6px;border-radius:12px;border:2px solid var(--line);background:#fff;text-decoration:none;color:var(--ink)}
.sib span.i{height:84px;display:flex;align-items:center;justify-content:center;background:#fff;border-radius:8px;padding:4px}
.sib img{max-width:100%;max-height:100%;object-fit:contain}
.sib b{font-size:13px;line-height:1.2}

/* mistakes */
.mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:16px;align-items:start}
.mcard{overflow:hidden;display:flex;flex-direction:column}
.mcard .pic{position:relative}
.mcard img{display:block;width:100%;aspect-ratio:3/2;object-fit:cover;background:#eee}
.mcard .sim{position:absolute;left:8px;bottom:8px;font-size:11px;font-weight:700;background:rgba(0,0,0,.55);color:#fff;border-radius:999px;padding:2px 8px}
.mcard .bd{padding:14px 16px 16px;display:flex;flex-direction:column;gap:10px}
.mcard h2{font-size:21px;font-weight:800}
.mcard .mis{margin:0;font-size:14px;background:#FFF4EC;border-radius:10px;padding:8px 10px}
.mcard .k{margin:0 0 4px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.mcard ul{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:4px;font-size:14px}

/* manual */
.mtop{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:6px 16px}
.stage{position:relative}
.pagebox{contain:strict;overscroll-behavior:contain;position:relative;overflow:auto;height:clamp(320px,72vh,780px);background:#4E5B63;border-radius:16px;display:flex;align-items:center;justify-content:center;touch-action:pan-y}
.pagebox.zoomed{align-items:flex-start;justify-content:flex-start;touch-action:auto}
.pagebox img{display:block;max-width:100%;max-height:100%;margin:auto;background:#fff;user-select:none;transition:opacity .15s ease}
.perr{position:absolute;inset:auto 0 45% 0;margin:0;text-align:center;color:#fff;font-weight:700;pointer-events:none}
.pagebox.zoomed img{max-width:none;max-height:none;height:auto}
.pagebox img.loading{opacity:.5}
.spin{pointer-events:none;position:absolute;top:14px;right:14px;width:26px;height:26px;border-radius:50%;border:3px solid rgba(255,255,255,.35);border-top-color:#fff;animation:rsSpin .7s linear infinite;display:none}
.spin.on{display:block}
.arrow{z-index:3;position:absolute;top:50%;transform:translateY(-50%);width:52px;height:52px;border-radius:50%;border:0;cursor:pointer;font-size:30px;line-height:1;font-weight:700;background:rgba(14,58,70,.85);color:#fff;box-shadow:0 2px 10px rgba(0,0,0,.25)}
.arrow:hover{background:var(--brand)}
.arrow:disabled{background:rgba(14,58,70,.25);cursor:default}
.arrow.l{left:10px}.arrow.r{right:10px}
.mbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;padding:8px 12px}
.mbar label{flex:1 1 260px;display:flex;align-items:center;gap:10px;font-size:14px;font-weight:700;min-height:44px}
.mbar input[type=range]{flex:1;min-width:0;accent-color:var(--blue)}
.mbar .pn{flex:none;min-width:70px;text-align:right;font-variant-numeric:tabular-nums}
"""

APP_JS = r"""(function () {
  'use strict';
  // An image loaded straight from its supplied link that fails (site down, link changed) -> say so instead of a broken picture.
  document.addEventListener('error', function (e) {
    var im = e.target;
    if (!im || im.tagName !== 'IMG' || !im.classList.contains('remote')) return;
    var box = document.createElement('span');
    box.className = 'none';
    box.innerHTML = 'Image could not<br>be loaded';
    box.style.cssText = 'display:flex;align-items:center;justify-content:center;text-align:center;width:100%;height:100%;min-height:120px;color:#8A3D00;font-weight:700';
    im.replaceWith(box);
  }, true);
  var D = window.RS;
  var view = document.getElementById('view');
  var T = D.topics;
  var byId = {};
  var slug = function (id) { return String(id).replace(/_/g, '-'); };
  D.specimens.forEach(function (s, i) { s.index = i; byId[s.id] = s; byId[slug(s.id)] = s; });
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var st = { q: '', cat: 'all', mcat: 'all', mode: 'both', linked: true, labels: true, last: D.specimens[0].id, mz: 1, page: 2 };
  try { var saved = JSON.parse(localStorage.getItem('rs-view') || '{}'); if (saved.labels === false) st.labels = false; } catch (e) {}
  function remember() { try { localStorage.setItem('rs-view', JSON.stringify({ labels: st.labels })); } catch (e) {} }

  // ------------------------------------------------------------------ routing
  function parse() {
    // addresses are plain names (#specimens, #viewer-img-016-03, #manual-36): letters, digits and hyphens only,
    // so they survive being shared, bookmarked or opened inside a host page
    var raw = (location.hash || '#specimens').replace(/^#\/?/, '');
    var cut = raw.search(/[-\/]/);
    var h = cut < 0 ? [raw] : [raw.slice(0, cut), raw.slice(cut + 1)];
    return { tab: h[0] || 'specimens', arg: decodeURIComponent(h[1] || '') };
  }
  var current = '';
  function route() {
    var r = parse();
    var key = r.tab + '/' + r.arg;
    if (key === current) return;
    var sameTab = current.split('/')[0] === r.tab;
    current = key;
    document.querySelectorAll('.nav a').forEach(function (a) {
      if (a.dataset.tab === r.tab) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    if (r.tab !== 'manual') M = null;
    if (r.tab === 'viewer') renderViewer(byId[r.arg] || byId[st.last]);
    else if (r.tab === 'mistakes') renderMistakes();
    else if (r.tab === 'manual') renderManual(parseInt(r.arg, 10) || st.page);
    else renderSpecimens();
    if (!sameTab) {
      view.classList.remove('enter'); void view.offsetWidth; view.classList.add('enter');
      window.scrollTo({ top: 0, behavior: 'auto' });
    }
  }
  window.addEventListener('hashchange', route);
  function go(hash) { if (location.hash !== hash) location.hash = hash; }
  function fadeImgs(root) {
    root.querySelectorAll('img.fade').forEach(function (im) {
      if (im.complete && im.naturalWidth) im.classList.add('ok');
      else im.addEventListener('load', function () { im.classList.add('ok'); }, { once: true });
    });
  }
  function preload(srcs) { srcs.forEach(function (s) { if (s) { var i = new Image(); i.src = s; } }); }

  // ------------------------------------------------------------------ specimens
  function renderSpecimens() {
    var tiles = Object.keys(T).map(function (k) {
      return '<button class="tile" type="button" data-cat="' + k + '"><span class="row"><span class="dot"></span></span><b>' + esc(T[k].name) + '</b></button>';
    }).join('');
    view.innerHTML =
      '<section class="band hero"><div class="wrap band-in hero-in">' +
        '<div class="hero-l"><h1 class="h1">Explore the specimens</h1>' +
        '<p class="lead" style="color:#2A4A52;margin:0">Open any specimen to zoom into its diagram and, where we have one, a real photo side by side.</p>' +
        '<div class="search"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0E3A46" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>' +
        '<label class="sr" for="q">Search specimens</label><input id="q" type="search" placeholder="Search, e.g. nucleus or testis" value="' + esc(st.q) + '">' +
        '<button type="button" id="qx" aria-label="Clear search" hidden>&times;</button></div></div>' +
        '<div class="hero-r"><p class="kicker">Browse by topic</p><div class="tiles">' + tiles + '</div></div>' +
      '</div></section>' +
      '<main class="wrap main"><div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px"><p id="count" style="margin:0;font-weight:700" aria-live="polite"></p>' +
      '<button type="button" class="chip" id="showall" hidden style="min-height:36px;font-size:13px">Show all &times;</button></div>' +
      '<div id="none" class="empty" hidden></div><div class="grid" id="grid"></div></main>';
    var q = view.querySelector('#q');
    q.addEventListener('input', function () { st.q = q.value; drawGrid(); });
    view.querySelector('#qx').addEventListener('click', function () { st.q = ''; q.value = ''; drawGrid(); q.focus(); });
    view.querySelector('#showall').addEventListener('click', function () { st.q = ''; q.value = ''; st.cat = 'all'; drawGrid(); });
    view.querySelectorAll('.tile').forEach(function (b) {
      b.addEventListener('click', function () { st.cat = st.cat === b.dataset.cat ? 'all' : b.dataset.cat; drawGrid(); });
    });
    drawGrid();
  }
  function matches(s, ql) { return !ql || (s.caption + ' ' + s.labels.join(' ') + ' ' + T[s.cat].name + ' ' + s.ex).toLowerCase().indexOf(ql) >= 0; }
  function drawGrid() {
    var ql = st.q.trim().toLowerCase();
    var base = D.specimens.filter(function (s) { return matches(s, ql); });
    var shown = base.filter(function (s) { return st.cat === 'all' || s.cat === st.cat; });
    view.querySelectorAll('.tile').forEach(function (b) {
      var t = T[b.dataset.cat], on = st.cat === b.dataset.cat;
      b.setAttribute('aria-pressed', on);
      b.style.background = on ? t.fg : '#fff'; b.style.color = on ? '#fff' : t.fg; b.style.borderColor = on ? t.fg : 'transparent';
      b.querySelector('.dot').style.background = on ? '#fff' : t.dot;
    });
    view.querySelector('#qx').hidden = !st.q;
    view.querySelector('#showall').hidden = st.cat === 'all' && !ql;
    view.querySelector('#count').textContent = (st.cat !== 'all' ? T[st.cat].name : '') + (st.cat !== 'all' && ql ? ' \u00b7 ' : '') + (ql ? 'matching \u201c' + st.q.trim() + '\u201d' : '');
    view.querySelector('#count').hidden = st.cat === 'all' && !ql;
    var none = view.querySelector('#none');
    none.hidden = shown.length > 0;
    none.innerHTML = '<p style="margin:0;font-weight:700">Nothing matches “' + esc(st.q) + '”.</p><p style="margin:6px 0 0;font-size:14px;color:#4A5A63">Try a specimen (“testis”) or a part (“nucleus”).</p>';
    var grid = view.querySelector('#grid');
    grid.innerHTML = shown.map(function (s) {
      var t = T[s.cat];
      return '<a class="card" href="#viewer-' + slug(s.id) + '"><span class="th2"><span class="half" style="background:' + t.bg + '"><img class="fade" loading="lazy" decoding="async" src="' + s.img + '" alt=""></span></span>' +
        '<span class="bd"><span class="nm">' + esc(s.caption) + '</span><span style="display:flex;flex-wrap:wrap;gap:6px">' +
        '<span class="pill" style="background:' + t.bg + ';color:' + t.fg + '">' + esc(t.name) + '</span></span></span></a>';
    }).join('');
    fadeImgs(grid);
  }

  // ------------------------------------------------------------------ viewer
  function photoPanelMissing(s) {
    var p = s.photoInfo || {};
    var msg = p.status === 'held_back' ? 'Not shown: ' + p.note
      : p.status === 'no_link' ? 'No image link was supplied for this specimen.'
      : 'The supplied image could not be downloaded' + (p.note ? ' (' + p.note + ')' : '') + '.';
    return '<section class="box panel" data-kind="missing"><div class="pbar" style="background:#FFF0CC"><span class="ttl" style="color:#6B4600">Supplied image</span></div>' +
      '<div class="vp missing"><div class="miss"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#8A5A00" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-8 8"/></svg>' +
      '<p class="t">Image not available here</p><p class="s">' + esc(msg) + '</p>' +
      (s.link ? '<a class="btn" href="' + esc(s.link) + '" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;text-decoration:none;color:inherit">Open the supplied source &nearr;</a>' : '') +
      '</div></div><p class="hint">&nbsp;</p></section>';
  }
  function renderViewer(s) {
    st.last = s.id;
    var t = T[s.cat];
    var mode = s.photo ? st.mode : 'both';
    var sibs = D.specimens.filter(function (x) { return x.exn === s.exn; });
    var opts = D.specimens.map(function (x) { return '<option value="' + x.id + '"' + (x.id === s.id ? ' selected' : '') + '>' + esc(x.caption + ' - ' + T[x.cat].name) + '</option>'; }).join('');
    var seg = s.photo ? '<div class="seg" role="group" aria-label="View">' + [['diagram', 'Diagram'], ['both', 'Side by side'], ['photo', 'Supplied image']].map(function (m) {
      return '<button type="button" data-mode="' + m[0] + '" aria-pressed="' + (mode === m[0]) + '">' + m[1] + '</button>'; }).join('') + '</div>' : '';
    var kinds = mode === 'both' ? ['diagram', 'photo'] : [mode];
    var panels = kinds.map(function (kind) {
      var photo = kind === 'photo';
      if (photo && !s.photo) return photoPanelMissing(s);
      var src = photo ? s.photo.src : (s.imgPlain && !st.labels ? s.imgPlain : s.img);
      return '<section class="box panel" data-kind="' + kind + '"><div class="pbar" style="background:' + (photo ? '#FFF0CC' : '#E3EEFB') + '">' +
        '<span class="ttl" style="color:' + (photo ? '#6B4600' : '#123F73') + '">' + (photo ? 'Supplied image' : 'Lab manual diagram') +
        (!photo && s.imgPlain ? '<label class="toggle"><input type="checkbox" class="lbl"' + (st.labels ? ' checked' : '') + '> Show labels</label>' : '') + '</span>' +
        '<span class="zoom" role="group" aria-label="Zoom"><button class="icon-btn" type="button" data-z="out" aria-label="Zoom out">&minus;</button><span class="pct">100%</span>' +
        '<button class="icon-btn" type="button" data-z="in" aria-label="Zoom in">+</button><button class="btn" type="button" data-z="fit" style="min-height:42px">Fit</button></span></div>' +
        '<div class="vp" style="background:' + (photo ? '#1B1F22' : '#fff') + '"><div class="inner"><img class="fade' + (photo && s.photo.remote ? ' remote' : '') + '" draggable="false" decoding="async" referrerpolicy="no-referrer" src="' + esc(src) + '" alt="' + (photo ? 'Supplied image: ' : 'Diagram: ') + esc(s.caption) + '"></div></div>' +
        '<p class="hint">Use + or double-click to zoom in, &minus; to zoom out. Drag to move. Pinch or Ctrl + scroll also zoom.</p></section>';
    }).join('');
    var labels = s.labels.length ? '<ul class="labels">' + s.labels.map(function (l) { return '<li style="background:' + t.bg + ';color:' + t.fg + '">' + esc(l) + '</li>'; }).join('') + '</ul>'
      : '<p style="margin:0;font-size:14px;color:#4A5A63">This diagram has no printed labels. See the source below.</p>';
    var host = function (u) { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
    var pi = s.photoInfo || {};
    var photoSrc = (s.link ? '<p class="s">Source: <a href="' + esc(s.link) + '" target="_blank" rel="noopener" style="color:#8A5A00;font-weight:700">' + esc(host(s.link) || 'supplied link') + ' &nearr;</a>' +
        (pi.resolved && pi.resolved !== s.link && host(pi.resolved) !== host(s.link) ? ' (image file from ' + esc(host(pi.resolved)) + ')' : '') + '</p>' : '<p class="s">No link supplied.</p>') +
      '<p class="s">Licence / credit (as supplied): ' + (s.licence ? esc(s.licence) : '<i>not provided</i>') + '</p>' +
      (s.magnification ? '<p class="s">Magnification (as supplied): ' + esc(s.magnification) + '</p>' : '') +
      (s.photo ? '' : '<p class="s" style="color:#8A3D00;font-weight:700">' + (pi.status === 'held_back' ? 'Held back: ' + esc(pi.note) : 'Image not available yet.') + '</p>');
    view.innerHTML = '<main class="wrap main">' +
      '<div class="vbar"><a class="btn" href="#specimens" style="display:inline-flex;align-items:center;text-decoration:none;color:inherit">&larr; All specimens</a>' +
      '<label class="sr" for="pick">Choose a specimen</label><select id="pick">' + opts + '</select>' +
      '<button class="icon-btn" type="button" id="prev" aria-label="Previous specimen">&lsaquo;</button><button class="icon-btn" type="button" id="next" aria-label="Next specimen">&rsaquo;</button></div>' +
      '<div class="vhead"><div style="min-width:0"><p class="meta"><span class="pill" style="background:' + t.bg + ';color:' + t.fg + '">' + esc(t.name) + '</span> ' + esc(s.ex) + '</p>' +
      '<h1>' + esc(s.caption) + '</h1>' + (s.desc ? '<p class="desc">' + esc(s.desc) + '</p>' : '') + '</div>' + seg + '</div>' +
      '<div class="panels">' + panels + '</div>' +
      (mode === 'both' && s.photo ? '<label style="display:inline-flex;align-items:center;gap:8px;min-height:44px;font-size:14px;font-weight:700;cursor:pointer;align-self:flex-start"><input type="checkbox" id="link"' + (st.linked ? ' checked' : '') + ' style="width:18px;height:18px;accent-color:#0E3A46"> Zoom and move both images together</label>' : '') +
      '<div class="cols"><section class="box sec"><h2>Labels in the diagram</h2>' + labels + '</section>' +
      '<section class="box sec"><h2>Sources</h2>' +
        '<div class="src"><span class="ic" style="background:#E3EEFB"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1E5FA8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4h11l5 5v11H4z"/><path d="M15 4v5h5"/></svg></span>' +
        '<div><p class="t">Diagram</p><p class="s">Lab manual, page ' + s.page + '</p><a class="linkbtn" style="color:#1E5FA8" href="#manual-' + s.pdf + '">Open page ' + s.page + ' of the manual &rarr;</a></div></div>' +
        '<div class="src"><span class="ic" style="background:#FFF0CC"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8A5A00" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="6" width="18" height="14" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8 6l1.5-2h5L16 6"/></svg></span>' +
        '<div style="min-width:0;overflow-wrap:anywhere"><p class="t">Supplied image</p>' + photoSrc + '</div></div></section></div>' +
      (sibs.length > 1 ? '<section><h2 style="font-size:20px;font-weight:800;margin-bottom:10px">More from ' + esc(s.ex) + '</h2><div class="sibs">' + sibs.map(function (x) {
        var on = x.id === s.id;
        return '<a class="sib" href="#viewer-' + slug(x.id) + '"' + (on ? ' aria-current="true" style="border-color:' + t.fg + ';background:' + t.bg + '"' : '') + '><span class="i"><img class="fade" loading="lazy" decoding="async" src="' + x.img + '" alt=""></span><b>' + esc(x.caption) + '</b></a>';
      }).join('') + '</div></section>' : '') +
      '</main>';
    fadeImgs(view);
    preload([s.imgPlain, s.photo && s.photo.src]);
    var i = s.index, n = D.specimens.length;
    view.querySelector('#pick').addEventListener('change', function (e) { go('#viewer-' + slug(e.target.value)); });
    view.querySelector('#prev').addEventListener('click', function () { go('#viewer-' + slug(D.specimens[(i - 1 + n) % n].id)); });
    view.querySelector('#next').addEventListener('click', function () { go('#viewer-' + slug(D.specimens[(i + 1) % n].id)); });
    view.querySelectorAll('.seg button').forEach(function (b) { b.addEventListener('click', function () { st.mode = b.dataset.mode; renderViewer(s); }); });
    var zs = [];
    var linkBox = view.querySelector('#link');
    if (linkBox) linkBox.addEventListener('change', function () { st.linked = linkBox.checked; zs.forEach(function (z) { z.set(1, 0, 0); }); });
    var lb = view.querySelector('.lbl');
    if (lb) lb.addEventListener('change', function () {
      st.labels = lb.checked; remember();
      var im = view.querySelector('.panel[data-kind=diagram] img');
      im.src = st.labels ? s.img : s.imgPlain;
    });
    view.querySelectorAll('.panel').forEach(function (p) { if (p.dataset.kind !== 'missing') zs.push(makeZoom(p, zs, function () { return mode === 'both' && st.linked; })); });
  }

  function makeZoom(panel, all, isLinked) {
    var vp = panel.querySelector('.vp'), inner = panel.querySelector('.inner'), pct = panel.querySelector('.pct');
    var z = { s: 1, x: 0, y: 0 };
    function apply() {
      inner.style.transform = 'translate(' + z.x + '%,' + z.y + '%) scale(' + z.s + ')';
      pct.textContent = Math.round(z.s * 100) + '%';
      vp.classList.toggle('zoomed', z.s > 1);
    }
    function clamp() { var lim = Math.max(0, (z.s - 1) * 50); z.x = Math.max(-lim, Math.min(lim, z.x)); z.y = Math.max(-lim, Math.min(lim, z.y)); }
    var api = {
      set: function (s, x, y, fromPeer) {
        z.s = Math.max(0.5, Math.min(8, s)); z.x = x; z.y = y; clamp(); apply();
        if (!fromPeer && isLinked()) all.forEach(function (o) { if (o !== api) o.set(z.s, z.x, z.y, true); });
      },
      get: function () { return z; }
    };
    panel.querySelector('[data-z=in]').addEventListener('click', function () { api.set(z.s * 1.25, z.x, z.y); });
    panel.querySelector('[data-z=out]').addEventListener('click', function () { api.set(z.s * 0.8, z.x, z.y); });
    panel.querySelector('[data-z=fit]').addEventListener('click', function () { api.set(1, 0, 0); });
    vp.addEventListener('dblclick', function () { if (z.s < 2) api.set(2.5, z.x, z.y); else api.set(1, 0, 0); });
    vp.addEventListener('wheel', function (e) {
      if (!e.ctrlKey) return;  // plain scrolling still scrolls the page; Ctrl+wheel / trackpad pinch zooms
      e.preventDefault();
      api.set(z.s * (e.deltaY < 0 ? 1.12 : 0.89), z.x, z.y);
    }, { passive: false });
    var pts = {}, start = null;
    vp.addEventListener('pointerdown', function (e) {
      pts[e.pointerId] = { x: e.clientX, y: e.clientY };
      var ids = Object.keys(pts);
      if (ids.length === 2) {
        var a = pts[ids[0]], b = pts[ids[1]];
        start = { pinch: Math.hypot(a.x - b.x, a.y - b.y), s: z.s, x: z.x, y: z.y };
      } else if (z.s > 1) {
        start = { px: e.clientX, py: e.clientY, x: z.x, y: z.y };
        vp.classList.add('drag');
      } else { start = null; return; }
      try { vp.setPointerCapture(e.pointerId); } catch (err) {}
    });
    vp.addEventListener('pointermove', function (e) {
      if (!pts[e.pointerId] || !start) return;
      pts[e.pointerId] = { x: e.clientX, y: e.clientY };
      var ids = Object.keys(pts);
      if (start.pinch && ids.length === 2) {
        var a = pts[ids[0]], b = pts[ids[1]];
        api.set(start.s * Math.hypot(a.x - b.x, a.y - b.y) / start.pinch, start.x, start.y);
      } else if (start.px != null) {
        api.set(z.s, start.x + (e.clientX - start.px) / vp.clientWidth * 100, start.y + (e.clientY - start.py) / vp.clientHeight * 100);
      }
    });
    function end(e) { delete pts[e.pointerId]; if (!Object.keys(pts).length) { start = null; vp.classList.remove('drag'); } }
    vp.addEventListener('pointerup', end);
    vp.addEventListener('pointercancel', end);
    apply();
    return api;
  }

  // ------------------------------------------------------------------ mistakes
  var ML = { mount: ['Mounting', '#124E9C', '#E2EDFB'], stain: ['Staining', '#A3144E', '#FCE6EE'], dirt: ['Dirt on slide or lens', '#5B4A00', '#FBF1C7'],
             scope: ['Microscope settings', '#5B2DA8', '#EEE6FB'], prepared: ['Prepared slides', '#1F6B2A', '#E3F3E5'] };
  function renderMistakes() {
    var cats = [['all', 'All']].concat(Object.keys(ML).map(function (k) { return [k, ML[k][0]]; }));
    view.innerHTML = '<section class="band" style="background:var(--warm)"><div class="wrap band-in" style="display:flex;flex-direction:column;gap:12px">' +
      '<h1 class="h1" style="color:var(--warm-ink)">Is that really part of the cell?</h1>' +
      '<p class="lead" style="margin:0;color:#5A3420">Things that turn up on almost any slide and are easy to mistake for real structures &mdash; what each looks like, how to tell, and how to avoid it.</p>' +
      '<div class="chips" role="group" aria-label="Cause">' + cats.map(function (c) {
        return '<button type="button" class="chip" data-c="' + c[0] + '" style="border-color:#E9B997;color:var(--warm-ink)">' + c[1] + '</button>';
      }).join('') + '</div></div></section><main class="wrap main"><div class="mgrid" id="mg"></div></main>';
    view.querySelectorAll('.chip').forEach(function (b) { b.addEventListener('click', function () { st.mcat = b.dataset.c; drawMistakes(); }); });
    drawMistakes();
  }
  function drawMistakes() {
    view.querySelectorAll('.chip').forEach(function (b) {
      var on = b.dataset.c === st.mcat; b.setAttribute('aria-pressed', on);
      b.style.background = on ? 'var(--warm-ink)' : '#fff'; b.style.color = on ? '#fff' : 'var(--warm-ink)';
    });
    var mg = view.querySelector('#mg');
    mg.innerHTML = D.mistakes.filter(function (m) { return st.mcat === 'all' || m.cat === st.mcat; }).map(function (m) {
      var c = ML[m.cat];
      return '<article class="box mcard" id="' + m.id + '"><div class="pic"><img class="fade" loading="lazy" src="' + m.img + '" alt="Simulated microscope view: ' + esc(m.name.toLowerCase()) + '">' +
        (m.simulated ? '<span class="sim">Simulated view</span>' : '') + '</div><div class="bd">' +
        '<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px 10px"><h2>' + esc(m.name) + '</h2>' +
        '<span class="pill" style="font-size:12px;padding:3px 10px;background:' + c[2] + ';color:' + c[1] + '">' + c[0] + '</span></div>' +
        '<p class="mis"><b style="color:#8A3D00">Often mistaken for:</b> ' + esc(m.mistaken) + '</p>' +
        '<div><p class="k" style="color:#1E5FA8">How to spot it</p><ul>' + m.spot.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul></div>' +
        '<div><p class="k" style="color:#1F7A4D">How to fix it</p><ul>' + m.fix.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul></div>' +
        '</div></article>';
    }).join('');
    fadeImgs(mg);
  }

  // ------------------------------------------------------------------ manual
  // One canonical page number (st.page, a PDF position 1..N). Every way of turning the page
  // (arrows, keys, swipe, slider, exercise buttons, links) goes through turnTo(), which updates
  // the state at once and writes the address with replaceState - so rapid clicks never act on
  // a stale page and no hashchange storm builds up.
  var OFF = D.pageOffset;  // printed page = PDF page - OFF (null if the manual's numbering isn't consistent)
  function pageName(p) {
    if (OFF == null) return 'Sheet ' + p;
    var printed = p - OFF;
    return printed >= 1 ? 'Page ' + printed : (p === 1 ? 'Contents' : 'Front matter');
  }
  var heading = {};
  (D.manualEx || []).forEach(function (e) { heading[e[1]] = e[0]; });
  var exStarts = [];
  D.specimens.forEach(function (s) { if (!exStarts.some(function (e) { return e.exn === s.exn; })) exStarts.push({ exn: s.exn, ex: s.ex, pdf: s.pdf }); });
  exStarts.forEach(function (e) { if (heading[e.exn] && heading[e.exn] <= e.pdf) e.pdf = heading[e.exn]; });
  exStarts.sort(function (a, b) { return a.pdf - b.pdf; });
  var allStarts = exStarts.map(function (e) { return [e.pdf, e.exn]; }).concat(D.manualEx || []).sort(function (a, b) { return a[0] - b[0]; });
  function exerciseAt(p) {
    var c = null; allStarts.forEach(function (e) { if (e[0] <= p) c = e; });
    return c ? { exn: c[1], ex: (D.exerciseNames || {})[c[1]] || '' } : null;
  }
  var pageCache = new Map();  // src -> Image, at most 10 kept
  function cachePage(src) {
    if (!src || pageCache.has(src)) return;
    var im = new Image(); im.decoding = 'async'; im.src = src; pageCache.set(src, im);
    while (pageCache.size > 10) pageCache.delete(pageCache.keys().next().value);
  }
  var M = null;  // live elements of the manual view
  function renderManual(p) {
    var N = D.manual.length;
    if (!N) { view.innerHTML = '<main class="wrap main"><h1 class="h1">Lab manual</h1><p>The manual pages have not been prepared yet - run Scripts/run_all.py.</p></main>'; M = null; return; }
    if (M && view.contains(M.img)) { turnTo(p, true); return; }
    view.innerHTML = '<main class="wrap main" style="max-width:1180px">' +
      '<div class="mtop"><h1 class="h1" style="color:#123F73;font-size:clamp(28px,5vw,40px)">Lab manual</h1><p style="margin:0;font-size:15px;color:#4A5A63"><b id="plabel" style="color:#13212B"></b><span id="exlabel"></span></p></div>' +
      '<div class="chips" id="exchips" role="group" aria-label="Exercises">' +
        '<button type="button" class="chip" data-p="1" style="border-color:#C3D7F2;color:#123F73">Contents</button>' +
        exStarts.map(function (e) { return '<button type="button" class="chip" data-p="' + e.pdf + '" data-ex="' + e.exn + '" style="border-color:#C3D7F2;color:#123F73">' + esc(e.ex) + '</button>'; }).join('') +
      '</div>' +
      '<div class="stage"><div class="pagebox" id="pbox"><img id="pg" draggable="false" decoding="async" alt=""><span class="spin" id="spin" aria-hidden="true"></span><p class="perr" id="perr" hidden>This page could not be loaded.</p></div>' +
      '<button class="arrow l" type="button" id="pprev" aria-label="Previous page">&lsaquo;</button><button class="arrow r" type="button" id="pnext" aria-label="Next page">&rsaquo;</button></div>' +
      '<div class="box mbar"><label><span style="flex:none">Page</span><input type="range" id="slider" min="1" max="' + N + '" aria-label="Go to page"><span class="pn" id="pnum"></span></label>' +
      '<span class="zoom" role="group" aria-label="Zoom page"><button class="icon-btn" type="button" id="mzo" aria-label="Zoom out">&minus;</button><span class="pct" id="mpct">100%</span>' +
      '<button class="icon-btn" type="button" id="mzi" aria-label="Zoom in">+</button><button class="btn" type="button" id="mzf" style="min-height:42px">Fit</button></span></div>' +
      '<p style="margin:0;font-size:13px;color:#4A5A63;text-align:center">Use &lsaquo; &rsaquo;, the slider, the arrow keys, or swipe the page to turn it.</p></main>';
    M = { img: view.querySelector('#pg'), box: view.querySelector('#pbox'), spin: view.querySelector('#spin'), err: view.querySelector('#perr'),
          slider: view.querySelector('#slider'), plabel: view.querySelector('#plabel'), exlabel: view.querySelector('#exlabel'),
          pnum: view.querySelector('#pnum'), prev: view.querySelector('#pprev'), next: view.querySelector('#pnext'),
          chips: Array.prototype.slice.call(view.querySelectorAll('#exchips .chip')), pct: view.querySelector('#mpct'), shown: 0 };
    M.prev.addEventListener('click', function () { turnTo(st.page - 1); });
    M.next.addEventListener('click', function () { turnTo(st.page + 1); });
    var raf = 0, pending = 0;
    M.slider.addEventListener('input', function () {   // live preview while dragging, at most once per frame
      pending = +M.slider.value;
      if (!raf) raf = requestAnimationFrame(function () { raf = 0; showPage(pending); });
    });
    M.slider.addEventListener('change', function () { turnTo(+M.slider.value); });
    M.chips.forEach(function (b) { b.addEventListener('click', function () { turnTo(+b.dataset.p); }); });
    view.querySelector('#mzi').addEventListener('click', function () { zoomTo(st.mz * 1.25); });
    view.querySelector('#mzo').addEventListener('click', function () { zoomTo(st.mz * 0.8); });
    view.querySelector('#mzf').addEventListener('click', function () { zoomTo(1); });
    var sw = null;
    M.box.addEventListener('pointerdown', function (e) { sw = { x: e.clientX, y: e.clientY }; });
    M.box.addEventListener('pointerup', function (e) {
      if (!sw || st.mz > 1) { sw = null; return; }
      var dx = e.clientX - sw.x, dy = e.clientY - sw.y; sw = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) turnTo(st.page + (dx < 0 ? 1 : -1));
    });
    M.img.addEventListener('load', function () { M.spin.classList.remove('on'); M.img.classList.remove('loading'); M.err.hidden = true; });
    M.img.addEventListener('error', function () { M.spin.classList.remove('on'); M.img.classList.remove('loading'); M.err.hidden = false; });
    applyZoom();
    turnTo(p, true);
  }
  function turnTo(p, fromRoute) {
    var N = D.manual.length;
    p = Math.max(1, Math.min(N, p || 1));
    st.page = p;
    showPage(p);
    var h = '#manual-' + p;
    if (location.hash !== h) {
      current = 'manual/' + p;  // route() keys are tab/arg: the hashchange below (if any) is then a no-op
      try { history.replaceState(null, '', h); } catch (e) { location.hash = h; }
    }
  }
  function zoomTo(z) { st.mz = Math.max(0.5, Math.min(4, z)); applyZoom(); }
  function applyZoom() {
    if (!M) return;
    M.box.classList.toggle('zoomed', st.mz > 1);
    M.img.style.width = st.mz > 1 ? Math.round(st.mz * 100) + '%' : '';
    M.img.style.maxWidth = st.mz < 1 ? Math.round(st.mz * 100) + '%' : '';
    M.img.style.maxHeight = st.mz < 1 ? Math.round(st.mz * 100) + '%' : '';
    M.pct.textContent = Math.round(st.mz * 100) + '%';
  }
  function showPage(p) {
    if (!M) return;
    var N = D.manual.length;
    var src = D.manual[p - 1];
    if (M.shown !== p) {
      M.shown = p;
      var c = pageCache.get(src);
      var ready = c && c.complete && c.naturalWidth;
      M.spin.classList.toggle('on', !ready);
      M.img.classList.toggle('loading', !ready);
      M.err.hidden = true;
      M.img.src = src;
      M.img.alt = pageName(p) + ' of the lab manual';
      M.box.scrollTop = 0; M.box.scrollLeft = 0;
    }
    var cur = exerciseAt(p);
    M.plabel.textContent = pageName(p);
    M.exlabel.textContent = cur && cur.ex ? ' · ' + cur.ex : '';
    M.pnum.textContent = pageName(p).replace('Page ', 'p. ');
    if (+M.slider.value !== p) M.slider.value = p;
    M.prev.disabled = p <= 1;
    M.next.disabled = p >= N;
    M.chips.forEach(function (b) {
      var on = cur ? +b.dataset.ex === cur.exn : b.dataset.p === '1';
      if (b.getAttribute('aria-current') !== String(on)) {
        b.setAttribute('aria-current', on);
        b.style.background = on ? '#123F73' : '#fff'; b.style.color = on ? '#fff' : '#123F73';
      }
    });
    [p + 1, p + 2, p - 1].forEach(function (n) { if (n >= 1 && n <= N) cachePage(D.manual[n - 1]); });
    cachePage(src);
  }
  document.addEventListener('keydown', function (e) {
    if (parse().tab !== 'manual' || !M || /input|select|textarea/i.test((e.target.tagName || ''))) return;
    if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); turnTo(st.page + 1); }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); turnTo(st.page - 1); }
  });

  route();
})();
"""
