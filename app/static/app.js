"use strict";
/* CircuLoop dashboard. Sections:  helpers | charts | pieces | views | interactions | chat | start */

/* ------------------------------------------------------------------ helpers */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const num = (n, d = 1) => Number(n).toLocaleString("en-US", {minimumFractionDigits: d, maximumFractionDigits: d});
const int = n => Number(n).toLocaleString("en-US");
const C = {ink:"#141211", peach:"#F7B08A", peach2:"#EE956A", peach3:"#FBD3BC", peach4:"#FDE9DC", alert:"#D4411E", line:"#EBCDBB", muted:"#7a6a61", card:"#FFF8F3"};
const NAMES = {lag1:"Usage 15 min ago", lag4:"Usage 1 hour ago", lag96:"Usage same time yesterday", roll4:"Average of last hour",
               hour:"Time of day", dow:"Day of week", weekend:"Weekend"};

const ICON = {
  overview:'<path d="M4 4h7v7H4zM13 4h7v4h-7zM13 11h7v9h-7zM4 14h7v6H4z"/>',
  flow:'<circle cx="5" cy="6" r="2.2"/><circle cx="19" cy="6" r="2.2"/><circle cx="12" cy="18" r="2.2"/><path d="M7.2 6h9.6M6.4 7.8l4.4 8.4M17.6 7.8l-4.4 8.4"/>',
  bf:'<path d="M7 20V9l2-5h6l2 5v11zM7 13h10"/>',
  bof:'<path d="M6 9h12l-1.5 11h-9zM9 9V4h6v5"/>',
  energy:'<path d="M13 3L5 13h6l-1 8 8-10h-6z"/>',
  lab:'<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  decisions:'<path d="M5 12.5l4 4 10-10"/>',
  records:'<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/>',
};
const NAV = [["overview","Overview"],["flow","Circular flow"],["bf","Blast furnace"],["bof","LD converter"],
             ["energy","Plant energy"],["lab","Scenario lab"],["decisions","Decisions"],["records","Records & sources"]];
const TITLES = {
  overview:["Plant overview","How the plant is running and where its by-products are going."],
  flow:["Circular flow","Follow material through the plant and see where it loops back. Select any stage."],
  bf:["Blast furnace","Iron making and BF slag."],
  bof:["LD converter","Steel making and LD slag."],
  energy:["Plant energy","Electricity use, the forecast and the reason behind it."],
  lab:["Scenario lab","Change an assumption and see how the circularity figures respond."],
  decisions:["Decisions","Recommended actions and what has been decided."],
  records:["Records & sources","Where every number comes from."],
};

const S = {view:"overview", idx:1000, max:0, playing:true, timer:null, busy:false, ov:null, exp:null, ser:null, hourly:null,
           flow:null, graph:null, cache:{}, decisions:{}, log:[], flowSel:"ldslag", lab:{sid:"bof", gen:0, buy:0, rec:0}, chat:[], lastView:null};
const ACTS = {};   // action id -> action

async function api(path, body) {
  const r = await fetch(path, body ? {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)} : undefined);
  if (!r.ok) throw new Error(path + " returned " + r.status);
  return r.json();
}
function fail(e) { $("view").innerHTML = `<div class="err"><b>Could not load data.</b><br>${esc(e.message)}<br>Is the server running and the model trained?</div>`; }
const tag = t => `<span class="tag ${esc(t)}">${esc(t)}</span>`;

/* ------------------------------------------------------------------- charts */
function donut(parts, opt) {
  const size = opt.size || 168, sw = opt.stroke || 24, r = (size - sw) / 2, cx = size / 2, circ = 2 * Math.PI * r;
  const total = parts.reduce((a, p) => a + p.v, 0) || 1;
  let acc = 0, segs = "";
  parts.filter(p => p.v > 0).forEach(p => {
    const len = Math.max(p.v / total * circ - 2, 0.5);
    segs += `<circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${p.c}" stroke-width="${sw}" stroke-dasharray="${len} ${circ - len}" stroke-dashoffset="${-acc}" transform="rotate(-90 ${cx} ${cx})"><title>${esc(p.k)}: ${int(p.v)} t</title></circle>`;
    acc += p.v / total * circ;
  });
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(opt.label || "Donut chart")}">
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${C.peach4}" stroke-width="${sw}"/>${segs}
    <text x="${cx}" y="${cx + 4}" text-anchor="middle" class="dtxt" ${opt.warn ? `style="fill:${C.alert}"` : ""}>${esc(opt.big)}</text>
    <text x="${cx}" y="${cx + 22}" text-anchor="middle" class="dsub">${esc(opt.small || "")}</text></svg>`;
}
function legend(parts, total) {
  return `<div class="legend">` + parts.filter(p => p.v > 0).map(p =>
    `<div><i style="background:${p.c}"></i>${esc(p.k)}<b>${int(p.v)} t</b><span class="p">${num(100 * p.v / total, 1)}%</span></div>`).join("") + `</div>`;
}
function streamParts(s) {
  const parts = [{k:"Sold / dispatched", v:s.sold_t, c:C.ink}, {k:"Recycled in plant", v:s.recycled_t, c:C.peach2}];
  if (s.gap_a > 0) parts.push({k:"No recorded use", v:s.gap_a, c:C.alert});
  return parts;
}
function streamDonut(s, size) {
  const parts = streamParts(s), over = s.diversion_pct > 100;
  return `<div class="donutwrap">${donut(parts, {size, big:num(s.diversion_pct, 1) + "%", small:"diverted", warn:over, label:s.name + " routing"})}
    <div style="flex:1;min-width:170px">${legend(parts, Math.max(s.generated_t, s.recycled_t + s.sold_t))}
    ${over ? `<p class="small" style="color:${C.alert};margin-top:8px">Recorded uses exceed generated tonnes by ${int(s.excess_t)} t.</p>` : ""}</div></div>`;
}
function ring(pct, over) {
  const r = 15, c = 2 * Math.PI * r, f = Math.min(pct, 100) / 100 * c;
  return `<svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="${r}" fill="none" stroke="#322c29" stroke-width="5"/>
    <circle cx="20" cy="20" r="${r}" fill="none" stroke="${over ? C.alert : C.peach}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${f} ${c - f}" transform="rotate(-90 20 20)"/></svg>`;
}
function gauge(e, peak) {
  const cx = 110, cy = 104, r = 84, P = Math.PI;
  const pt = v => { const f = Math.min(Math.max(v / peak, 0), 1); return [cx - r * Math.cos(P * f), cy - r * Math.sin(P * f)]; };
  const arc = v => { const [x, y] = pt(v); return `M${cx - r},${cy} A${r},${r} 0 0 1 ${x.toFixed(1)},${y.toFixed(1)}`; };
  const [bx, by] = pt(e.baseline_kwh), [ax, ay] = pt(e.actual_kwh), f = Math.min(e.baseline_kwh / peak, 1);
  const tick = `<line x1="${cx - (r - 12) * Math.cos(P * f)}" y1="${cy - (r - 12) * Math.sin(P * f)}" x2="${cx - (r + 12) * Math.cos(P * f)}" y2="${cy - (r + 12) * Math.sin(P * f)}" stroke="${C.alert}" stroke-width="3"/>`;
  return `<svg width="220" height="132" viewBox="0 0 220 132" role="img" aria-label="Forecast against peak load">
    <path d="M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}" fill="none" stroke="${C.peach4}" stroke-width="20" stroke-linecap="round"/>
    <path d="${arc(e.predicted_kwh)}" fill="none" stroke="${C.ink}" stroke-width="20" stroke-linecap="round"/>${tick}
    <circle cx="${ax}" cy="${ay}" r="7" fill="${C.peach2}" stroke="#fff" stroke-width="2"><title>Actual ${num(e.actual_kwh)} kWh</title></circle>
    <text x="${cx}" y="${cy - 6}" text-anchor="middle" class="dtxt">${num(e.predicted_kwh)}</text>
    <text x="${cx}" y="${cy + 14}" text-anchor="middle" class="dsub">kWh forecast</text>
    <text x="${cx - r}" y="${cy + 28}" text-anchor="middle" class="ax">0</text><text x="${cx + r}" y="${cy + 28}" text-anchor="middle" class="ax">${Math.round(peak)}</text></svg>
    <div class="cl"><span><i style="background:${C.ink}"></i>Forecast</span><span><i class="dot" style="background:${C.peach2}"></i>Actual</span><span><i style="background:${C.alert}"></i>Typical</span></div>`;
}

/* Material flow for one stream: left = generated, right = where it is recorded to go. */
function routeFlow(f) {
  const W = 620, H = 250, pad = 16, bw = 14, lx = 150, rx = 330, gap = 10;
  const parts = [{k:"Sold / dispatched", v:f.sold, c:C.ink, r:"#7a6a61"}, {k:"Recycled in plant", v:f.rec, c:C.peach2, r:C.peach2}];
  if (f.unrec > 0) parts.push({k:"No recorded use", v:f.unrec, c:C.alert, r:C.alert});
  const live = parts.filter(p => p.v > 0), totalR = live.reduce((a, p) => a + p.v, 0), max = Math.max(f.gen, totalR);
  const sc = (H - 2 * pad - (live.length - 1) * gap) / max, k = f.gen / totalR < 1 ? f.gen / totalR : 1;
  let ly = pad, ry = pad, out = "";
  live.forEach(p => {
    const lh = p.v * sc * k, rh = p.v * sc, mx = (lx + bw + rx) / 2;
    out += `<path d="M${lx + bw},${ly} C${mx},${ly} ${mx},${ry} ${rx},${ry} L${rx},${ry + rh} C${mx},${ry + rh} ${mx},${ly + lh} ${lx + bw},${ly + lh} Z" fill="${p.r}" fill-opacity=".3"><title>${esc(p.k)}: ${int(p.v)} t</title></path>
      <rect x="${rx}" y="${ry}" width="${bw}" height="${Math.max(rh, 2)}" rx="3" fill="${p.c}"/>
      <text x="${rx + bw + 10}" y="${ry + Math.max(rh, 18) / 2 - 2}" font-size="13" font-weight="600" fill="${C.ink}">${esc(p.k)}</text>
      <text x="${rx + bw + 10}" y="${ry + Math.max(rh, 18) / 2 + 13}" font-size="12" fill="${C.muted}">${int(p.v)} t &middot; ${num(100 * p.v / f.gen, 1)}%</text>`;
    ly += lh; ry += rh + gap;
  });
  out += `<rect x="${lx}" y="${pad}" width="${bw}" height="${Math.max(f.gen * sc, 2)}" rx="3" fill="${C.ink}"/>
    <text x="${lx - 10}" y="${pad + f.gen * sc / 2 - 2}" text-anchor="end" font-size="13" font-weight="600" fill="${C.ink}">${esc(f.name || "Generated")}</text>
    <text x="${lx - 10}" y="${pad + f.gen * sc / 2 + 13}" text-anchor="end" font-size="12" fill="${C.muted}">${int(f.gen)} t</text>`;
  const note = totalR > f.gen * 1.0005 ? `<text x="${lx - 10}" y="${H + 8}" font-size="12" fill="${C.alert}">Recorded uses exceed generated by ${int(totalR - f.gen)} t: the bands widen to the right.</text>` : "";
  return `<div class="scroll"><svg viewBox="0 0 ${W} ${H + 14}" width="100%" style="max-width:760px;min-width:440px" role="img" aria-label="Where the slag is recorded to go">${out}${note}</svg></div>`;
}

function chart() { return '<div class="chartbox" data-chart="series"></div>'; }
function hourChart() { return '<div class="hourbox" data-chart="hourly"></div>'; }
function drawCharts() {
  document.querySelectorAll("[data-chart]").forEach(b => {
    const w = Math.max(300, b.clientWidth);
    if (b.dataset.chart === "series") { b.innerHTML = svgSeries(S.ser, S.ov.model_mae, w); hover(b); }
    else if (b.dataset.chart === "hourly") b.innerHTML = svgHourly(S.hourly, S.exp, w);
  });
}
function svgSeries(ser, mae, W) {
  if (!ser) return "";
  const H = 250, L = 38, R = 10, T = 14, B = 26;
  const all = ser.actual.concat(ser.predicted), max = Math.max(...all, 1) * 1.08, n = ser.actual.length;
  const x = i => L + (W - L - R) * (n === 1 ? 0 : i / (n - 1)), y = v => T + (H - T - B) * (1 - v / max);
  const line = a => a.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  let grid = "";
  for (let g = 0; g <= 4; g++) { const v = max * g / 4; grid += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${C.line}"/><text class="ax" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v.toFixed(0)}</text>`; }
  let flags = "";
  ser.actual.forEach((a, i) => { if (Math.abs(a - ser.predicted[i]) > 2 * mae) flags += `<circle cx="${x(i)}" cy="${y(a)}" r="3.5" fill="${C.alert}"/>`; });
  const hh = t => t.slice(11, 16);
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" data-n="${n}" data-l="${L}" data-r="${R}" role="img" aria-label="Actual and forecast electricity, last 24 hours">
    ${grid}<polyline fill="none" stroke="${C.ink}" stroke-width="2.2" points="${line(ser.actual)}"/>
    <polyline fill="none" stroke="${C.peach2}" stroke-width="2.2" stroke-dasharray="6 4" points="${line(ser.predicted)}"/>${flags}
    <line x1="${x(n - 1)}" x2="${x(n - 1)}" y1="${T}" y2="${H - B}" stroke="${C.muted}" stroke-dasharray="2 4"/>
    <g class="hov" style="display:none"><line y1="${T}" y2="${H - B}" stroke="${C.ink}" stroke-width="1"/><circle r="4.5" fill="${C.ink}"/><circle r="4.5" fill="${C.peach2}"/></g>
    <text class="ax" x="${L}" y="${H - 7}">${hh(ser.times[0])}</text><text class="ax" x="${W - R}" y="${H - 7}" text-anchor="end">${hh(ser.times[n - 1])} (now)</text>
    <text class="ax" x="4" y="11">kWh</text></svg>
    <div class="cl"><span><i style="background:${C.ink}"></i>Actual</span><span><i style="background:${C.peach2}"></i>Forecast</span>
    <span><i class="dot" style="background:${C.alert}"></i>Differs by more than 2x typical error</span></div><div class="tip" style="display:none"></div>`;
}
function hover(box) {
  const svg = box.querySelector("svg"), tip = box.querySelector(".tip"), g = svg && svg.querySelector(".hov");
  if (!svg) return;
  const ser = S.ser, n = ser.actual.length, W = +svg.getAttribute("width"), L = +svg.dataset.l, R = +svg.dataset.r;
  const H = 250, T = 14, B = 26, max = Math.max(...ser.actual.concat(ser.predicted), 1) * 1.08, y = v => T + (H - T - B) * (1 - v / max);
  svg.addEventListener("mousemove", ev => {
    const rect = svg.getBoundingClientRect(), px = ev.clientX - rect.left;
    const i = Math.max(0, Math.min(n - 1, Math.round((px - L) / (W - L - R) * (n - 1))));
    const x = L + (W - L - R) * i / (n - 1);
    g.style.display = ""; g.querySelector("line").setAttribute("x1", x); g.querySelector("line").setAttribute("x2", x);
    const cs = g.querySelectorAll("circle"); cs[0].setAttribute("cx", x); cs[0].setAttribute("cy", y(ser.actual[i])); cs[1].setAttribute("cx", x); cs[1].setAttribute("cy", y(ser.predicted[i]));
    tip.style.display = ""; tip.style.left = x + "px"; tip.style.top = Math.min(y(ser.actual[i]), y(ser.predicted[i])) + "px";
    tip.innerHTML = `${esc(ser.times[i].slice(11, 16))}<br>Actual <b>${num(ser.actual[i])}</b> &middot; Forecast <b>${num(ser.predicted[i])}</b> kWh`;
  });
  svg.addEventListener("mouseleave", () => { g.style.display = "none"; tip.style.display = "none"; });
}
function svgHourly(h, e, W) {
  if (!h) return "";
  const H = 210, L = 34, R = 8, T = 10, B = 24, max = Math.max(...h.weekday, ...h.weekend, 1) * 1.1, bw = (W - L - R) / 24;
  const y = v => T + (H - T - B) * (1 - v / max), cur = e ? Math.floor(e.values.hour) : -1;
  let bars = "", dots = "";
  h.hours.forEach(i => {
    bars += `<rect x="${L + i * bw + 2}" y="${y(h.weekday[i])}" width="${bw - 4}" height="${H - B - y(h.weekday[i])}" rx="2" fill="${i === cur ? C.alert : C.ink}" opacity="${i === cur ? 1 : .85}"><title>${i}:00 weekday average ${h.weekday[i]} kWh</title></rect>`;
    dots += `<circle cx="${L + i * bw + bw / 2}" cy="${y(h.weekend[i])}" r="3" fill="${C.peach2}"><title>${i}:00 weekend average ${h.weekend[i]} kWh</title></circle>`;
  });
  let ax = ""; [0, 6, 12, 18, 23].forEach(i => ax += `<text class="ax" x="${L + i * bw + bw / 2}" y="${H - 6}" text-anchor="middle">${i}:00</text>`);
  for (let g = 0; g <= 3; g++) { const v = max * g / 3; ax += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="${C.line}"/><text class="ax" x="${L - 5}" y="${y(v) + 4}" text-anchor="end">${v.toFixed(0)}</text>`; }
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Average electricity by hour">${ax}${bars}${dots}</svg>
    <div class="cl"><span><i style="background:${C.ink}"></i>Weekday average</span><span><i class="dot" style="background:${C.peach2}"></i>Weekend average</span><span><i style="background:${C.alert}"></i>Current hour</span></div>`;
}

/* ------------------------------------------------------------------- pieces */
function openActions() {
  const list = (S.ov ? S.ov.actions : []).concat(S.exp ? S.exp.actions : []);
  list.forEach(a => ACTS[a.id] = a);
  return list;
}
function openCount() { return openActions().filter(a => a.priority !== "low" && !S.decisions[a.id]).length; }

function actionCard(a) {
  ACTS[a.id] = a;
  const d = S.decisions[a.id];
  return `<div class="act ${esc(a.priority)}"><div>${tag(a.priority)} <span class="small muted">${esc(a.section || "")}</span></div>
    <p class="t">${esc(a.text)}</p><p class="w">${esc(a.why)}</p>
    ${a.steps && a.steps.length ? `<details><summary>How to do it</summary><ol>${a.steps.map(s => `<li>${esc(s)}</li>`).join("")}</ol></details>` : ""}
    <div class="row">${d ? `<span class="done">Recorded: ${esc(d)}</span>` :
      `<button class="btn" data-act="${esc(a.id)}" data-dec="Acknowledged">Acknowledge</button><button class="btn alt" data-act="${esc(a.id)}" data-dec="Deferred">Defer</button>`}</div></div>`;
}
function actionsBlock(list, title) {
  return `<div class="card"><div class="ct">${title || "Recommended actions"}</div>${list.map(actionCard).join("") || '<p class="empty">No actions.</p>'}
    <p class="note">Rule-based and advisory. Nothing happens in the plant unless staff act.</p></div>`;
}
function statCards(stats) {
  return `<div class="stats">` + stats.map(s => `<div class="stat"><small>${esc(s.label)}</small><b>${esc(s.value)}</b><i>${esc(s.unit)}</i>
    <div class="meta">${tag(s.basis)}${s.note ? esc(s.note) : ""}</div></div>`).join("") + `</div>`;
}
function readingsTable(rs) {
  return `<div class="scroll"><table><tr><th>Reading of the records</th><th class="n">Gap (t)</th><th class="n">Gap %</th><th>Status</th></tr>` +
    rs.map(r => `<tr><td>${esc(r.reading)}</td><td class="n">${int(r.gap_t)}</td><td class="n">${num(r.gap_pct, 2)}%</td><td>${tag(r.status)}</td></tr>`).join("") +
    `</table></div><p class="note">Gap = tonnes generated minus tonnes with a recorded use. A negative gap means more is recorded as used than was generated. REVIEW asks a person to check the records; it does not say what is wrong.</p>`;
}
function explainBlock(e) {
  const rows = Object.entries(e.contributions).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const max = Math.max(...rows.map(r => Math.abs(r[1])), 0.01);
  return `<div class="expl">${esc(e.explanation)}</div>` + rows.map(([k, v]) => {
    const w = Math.abs(v) / max * 50, pos = v >= 0;
    return `<div class="bar"><span>${esc(NAMES[k] || k)}</span><span class="track"><span class="mid"></span><span class="fill" style="${pos ? "left:50%" : `left:${50 - w}%`};width:${w}%;background:${pos ? C.ink : C.peach2}"></span></span>
      <span class="v">${v >= 0 ? "+" : ""}${num(v)} kWh</span></div>`;
  }).join("") + `<p class="note">Dark bars push the forecast up, peach bars pull it down, compared with a typical reading of ${num(e.baseline_kwh)} kWh.</p>`;
}

/* -------------------------------------------------------------------- band */
function renderBand() {
  const ov = S.ov, e = S.exp; if (!ov || !e) return;
  const open = openCount(), nrev = ov.review_count;
  const say = `${e.status === "CHECK" ? "Energy use is outside the forecast range." : "Energy use is running as forecast."} ` +
    `${nrev ? nrev + " of 2 by-product streams need a records review." : "By-product records are consistent."} ` +
    `${open ? open + " action" + (open > 1 ? "s need" : " needs") + " a decision." : "No actions are waiting."}`;
  const tile = (label, big, unit, sub, warn, extra) => `<div class="tile ${warn ? "warn" : ""}">${extra || ""}<div><small>${label}</small><b>${big}<i>${unit}</i></b><span class="sub">${sub}</span></div></div>`;
  $("band").innerHTML = `<div class="say"><small>Right now</small><p>${esc(say)}</p></div>` +
    tile("Forecast", num(e.predicted_kwh), "kWh", "typical " + num(e.baseline_kwh)) +
    tile("Actual", num(e.actual_kwh), "kWh", (e.deviation_kwh >= 0 ? "+" : "") + num(e.deviation_kwh) + " vs forecast", e.status === "CHECK") +
    tile("BF slag", num(ov.bf.diversion_pct, 1), "%", ov.bf.status === "OK" ? "diverted, consistent" : "diverted, to review", ov.bf.status !== "OK", ring(ov.bf.diversion_pct, ov.bf.diversion_pct > 100)) +
    tile("LD slag", num(ov.bof.diversion_pct, 1), "%", ov.bof.status === "OK" ? "diverted, consistent" : "diverted, to review", ov.bof.status !== "OK", ring(ov.bof.diversion_pct, ov.bof.diversion_pct > 100)) +
    tile("Open actions", open, "", open ? "waiting for a decision" : "all handled", open > 0);
  renderNav();
}
function renderNav() {
  const open = openCount();
  $("nav").innerHTML = NAV.map(([id, label]) => {
    const lamp = id === "bf" && S.ov ? `<i class="lamp ${S.ov.bf.status}"></i>` : id === "bof" && S.ov ? `<i class="lamp ${S.ov.bof.status}"></i>` :
      id === "energy" && S.exp ? `<i class="lamp ${S.exp.status}"></i>` : id === "decisions" && open ? `<span class="badge">${open}</span>` : "";
    const ic = ICON[id] || ICON.overview;
    return `<button class="nv ${S.view === id ? "on" : ""}" data-view="${id}"><svg viewBox="0 0 24 24" aria-hidden="true">${ic}</svg><span class="l">${label}</span>${lamp}</button>`;
  }).join("");
}

/* ------------------------------------------------------------------- views */
function viewOverview() {
  const ov = S.ov, e = S.exp;
  const ins = ov.insights.map(i => `<div class="card insight ${esc(i.tone)}"><h4>${esc(i.title)}</h4><p>${esc(i.text)}</p></div>`).join("");
  const dc = (s, id) => `<div class="card link" data-view="${id}"><div class="ct"><span>${esc(s.name)} routing</span>${tag(s.status)}</div>${streamDonut(s, 150)}
    <p class="note">${int(s.generated_t)} t generated. Select for detail.</p></div>`;
  const top = openActions().filter(a => a.priority !== "low" && !S.decisions[a.id]).slice(0, 3);
  return `<div class="stack">
    <div class="grid3">${ins}</div>
    <div class="grid3">${dc(ov.bf, "bf")}${dc(ov.bof, "bof")}
      <div class="card link" data-view="energy"><div class="ct"><span>Energy forecast</span>${tag(e.status)}</div><div style="text-align:center">${gauge(e, ov.peak_kwh)}</div>
        <p class="note">Gauge runs to the highest reading in the test data (${num(ov.peak_kwh, 0)} kWh).</p></div></div>
    <div class="split">
      <div class="stack"><div class="card"><div class="ct">Plant electricity, last 24 hours (hover for values)</div>${chart()}</div>
        <div class="card"><div class="ct">Typical daily load</div>${hourChart()}<p class="note">Average of the whole year. The red bar is the hour of the current reading.</p></div></div>
      <div class="card"><div class="ct"><span>Needs a decision</span><button class="btn alt" data-view="decisions">All actions</button></div>
        ${top.map(actionCard).join("") || '<p class="empty">Nothing is waiting for a decision.</p>'}</div>
    </div>
    <div class="card dark"><div class="ct">How circularity works in the plant</div>
      <h3 style="color:#FDE9DC">Slag is a product only when someone uses it.</h3>
      <p style="max-width:70ch;color:#e6d6cc">Each stage of the plant makes a by-product. Circularity is the share of it that goes back into the process, or to a buyer with a confirmed use, instead of a stockpile or an unknown fate.</p>
      <p style="margin-top:12px"><button class="btn sel" data-view="flow">Open the circular flow map</button></p></div>
  </div>`;
}

async function viewFlow() {
  const f = S.flow || (S.flow = await api("/api/flow")), sel = S.flowSel, d = f.detail[sel], node = f.nodes.find(n => n.id === sel);
  const col = {main:C.ink, by:C.peach2, loop:C.ink};
  const edges = f.edges.map(e => {
    const w = e.width || (e.kind === "main" ? 3.5 : 4), hi = e.from === sel || e.to === sel;
    const dash = e.kind === "loop" ? 'stroke-dasharray="9 6"' : "";
    return `<path class="edge ${hi ? "hi" : ""}" d="${e.d}" stroke="${col[e.kind]}" stroke-width="${w}" ${dash} marker-end="url(#ah-${e.kind})"/>
      <path class="edge dots ${hi ? "hi" : ""}" d="${e.d}" style="stroke-width:${Math.max(2, w * .45)}"/>
      ${e.label ? `<text class="elabel ${hi ? "hi" : ""}" x="${e.lx}" y="${e.ly}" text-anchor="${e.anchor || "middle"}">${esc(e.label)}</text>` : ""}`;
  }).join("");
  const nodes = f.nodes.map(n => `<g class="node ${n.type} ${n.id === sel ? "sel" : ""}" data-flow="${n.id}" tabindex="0" role="button" aria-label="${esc(n.label)}">
    <rect x="${n.x - 78}" y="${n.y - 28}" width="156" height="56" rx="11"/><text x="${n.x}" y="${n.y + 5}" text-anchor="middle">${esc(n.label)}</text></g>`).join("");
  const mk = (k, c) => `<marker id="ah-${k}" viewBox="0 0 10 10" refX="8" refY="5" markerUnits="userSpaceOnUse" markerWidth="15" markerHeight="15" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${c}"/></marker>`;
  return `<div class="stack">
    <div class="card"><div class="ct"><span>Plant material flow</span><label class="small"><input type="checkbox" id="anim" ${S.noanim ? "" : "checked"}> Animate</label></div>
      <div class="flowwrap"><svg class="flowsvg ${sel ? "has-sel" : ""} ${S.noanim ? "noanim" : ""}" viewBox="0 36 1000 490" role="group" aria-label="Plant material flow diagram">
        <defs>${mk("main", C.ink)}${mk("by", C.peach2)}${mk("loop", C.ink)}</defs>${edges}${nodes}</svg></div>
      <div class="key"><span><i style="background:${C.ink}"></i>Process</span><span><i style="background:${C.peach}"></i>By-product</span>
        <span><i style="background:#fff;border:2px dashed ${C.ink}"></i>Recovery loop (material returns)</span><span><i style="background:#fff;border:2px solid ${C.ink}"></i>Buyer or product</span>
        <span>Band width on the slag routes is proportional to recorded tonnes.</span></div></div>
    <div class="card"><div class="ct"><span>Stage detail</span>${d.data.length ? "" : '<span class="small muted" style="text-transform:none;letter-spacing:0">Typical practice: the data has no figures for this stage</span>'}</div>
      <h3>${esc(node.label)}</h3>
      <div class="grid2" style="margin-top:6px"><div><p class="prose"><b>What happens.</b> ${esc(d.what)}</p><p class="prose" style="margin-top:8px"><b>How it is circular.</b> ${esc(d.circular)}</p>
        ${d.data.length ? `<dl class="dl">${d.data.map(x => `<dt>${esc(x.label)}</dt><dd>${esc(x.value)} ${tag(x.basis)}</dd>`).join("")}</dl>` : ""}</div>
      <div><div class="ct" style="margin-top:2px">What to decide here</div><ul class="tips">${d.decide.map(x => `<li>${esc(x)}</li>`).join("")}</ul>
        ${sel === "bfslag" || sel === "ldslag" || sel === "recov" || sel === "cement" || sel === "roads" ? `<p style="margin-top:12px"><button class="btn" data-lab="${sel === "bfslag" || sel === "cement" ? "bf" : "bof"}">Try it in the Scenario lab</button></p>` : ""}</div></div>
      <p class="note">${esc(f.source)}</p></div></div>`;
}

async function viewSection(id) {
  const v = S.cache[id] || (S.cache[id] = await api("/api/view/" + id)), s = v.stream;
  const f = {gen:s.generated_t, sold:s.sold_t, rec:s.recycled_t, unrec:Math.max(0, s.gap_a), name:s.name};
  return `<div class="stack">
    <div class="card"><div class="title-row"><h3 style="margin:0">${esc(v.title)}</h3>${tag(v.status)}</div><div class="small muted">Source: ${esc(v.source)}</div></div>
    <div class="grid2"><div class="card"><div class="ct">What is happening here</div><p class="prose">${esc(v.process)}</p></div>
      <div class="card"><div class="ct">How it is circular</div><p class="prose">${esc(v.how_circular)}</p><p class="note">${esc(v.circular_note)}</p></div></div>
    <div class="grid2"><div class="card"><div class="ct">Where the slag is recorded to go</div>${routeFlow(f)}</div>
      <div class="card"><div class="ct">Share of generated tonnes</div>${streamDonut(s, 170)}</div></div>
    <div class="card"><div class="ct">Circularity figures</div>${statCards(v.stats)}</div>
    <div class="card"><div class="ct">Record check</div>${readingsTable(v.readings)}</div>
    ${actionsBlock(v.actions)}
    <div class="card"><div class="ct">Test a change</div><p class="prose">See what happens to these figures if buyers leave, output changes or more is recovered in-plant.</p>
      <p style="margin-top:10px"><button class="btn" data-lab="${id}">Open the Scenario lab</button></p></div></div>`;
}

async function viewEnergy() {
  const v = S.cache.energy || (S.cache.energy = await api("/api/view/energy")), e = S.exp;
  return `<div class="stack">
    <div class="grid2"><div class="card"><div class="ct">What is happening here</div><p class="prose">${esc(v.process)}</p><p class="note">${esc(v.how_circular)}</p><p class="note">Source: ${esc(v.source)}</p></div>
      <div class="card"><div class="ct"><span>Forecast now</span>${tag(e.status)}</div><div style="text-align:center">${gauge(e, S.ov.peak_kwh)}</div>
        <p class="note" style="text-align:center">Reading at ${esc(e.time)}</p></div></div>
    <div class="card"><div class="ct">Actual and forecast, last 24 hours (hover for values)</div>${chart()}</div>
    <div class="grid2"><div class="card"><div class="ct">Typical daily load</div>${hourChart()}<p class="note">Average of the whole year. The red bar is the hour of the current reading.</p></div>
      <div class="card"><div class="ct">Model performance</div>${statCards(v.stats)}</div></div>
    <div class="card"><div class="ct">Why this forecast</div>${explainBlock(e)}</div>
    ${actionsBlock(e.actions, "Recommended actions for this reading")}</div>`;
}

function viewLab() {
  const L = S.lab;
  return `<div class="stack"><div class="card"><div class="ct"><span>Change an assumption</span><span class="pills"><button class="btn ${L.sid === "bf" ? "sel" : "alt"}" data-lab="bf">BF slag</button><button class="btn ${L.sid === "bof" ? "sel" : "alt"}" data-lab="bof">LD slag</button></span></div>
    <div class="grid3">
      <div class="sl"><label for="s-gen">Change in slag generation</label><input id="s-gen" type="range" min="-30" max="30" value="${L.gen}"><output id="o-gen">${L.gen}%</output></div>
      <div class="sl"><label for="s-buy">Share of sales lost (buyers drop out)</label><input id="s-buy" type="range" min="0" max="100" value="${L.buy}"><output id="o-buy">${L.buy}%</output></div>
      <div class="sl"><label for="s-rec">Extra share recovered in-plant</label><input id="s-rec" type="range" min="0" max="30" value="${L.rec}"><output id="o-rec">${L.rec}%</output></div></div>
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap"><button class="btn alt" id="labReset">Reset</button>
    <span class="note" style="margin:0">${tag("ASSUMED")} Estimates from stated assumptions. They show how the figures respond; they do not forecast the plant.</span></div></div>
    <div id="labOut" class="stack"><div class="card">Loading...</div></div></div>`;
}
async function runLab() {
  const L = S.lab;
  const d = await api(`/api/scenario/${L.sid}?gen_change=${L.gen}&buyer_loss=${L.buy}&extra_recovery=${L.rec}`), B = d.baseline, X = d.scenario;
  const mk = (r, extra) => {
    const parts = [{k:"Sold / dispatched", v:r.sold_t, c:C.ink}]; if (extra) parts.push({k:"Recovered in-plant", v:r.extra_recovered_t, c:C.peach2});
    parts.push({k:"Unmanaged", v:r.unmanaged_t, c:C.alert});
    return `<div class="donutwrap">${donut(parts, {size:150, stroke:22, big:num(r.diversion_pct, 1) + "%", small:"diverted", label:"Diversion"})}${legend(parts, r.generated_t)}</div>`;
  };
  const row = (label, a, c, unit, goodUp) => { const diff = c - a, cls = diff === 0 ? "" : ((diff > 0) === goodUp ? "up" : "down");
    const fmt = v => unit === "%" ? num(v, 2) + "%" : int(Math.round(v));
    return `<tr><td>${label}</td><td class="n">${fmt(a)}</td><td class="n">${fmt(c)}</td><td class="n delta ${cls}">${diff > 0 ? "+" : ""}${fmt(diff)}</td></tr>`; };
  $("labOut").innerHTML = `<div class="grid2"><div class="card"><div class="ct">Baseline: ${esc(d.stream)}</div>${mk(B, false)}</div><div class="card"><div class="ct">Scenario</div>${mk(X, true)}</div></div>
    <div class="card"><div class="ct">Material flow in the scenario</div><p class="small muted" style="margin:-4px 0 6px">Unmanaged = tonnes that still need a buyer or recovery route, or that would go to stockpile.</p>${routeFlow({gen:X.generated_t, sold:X.sold_t, rec:X.extra_recovered_t, unrec:X.unmanaged_t, name:d.stream})}</div>
    <div class="card"><div class="ct">Comparison</div><div class="scroll"><table><tr><th></th><th class="n">Baseline</th><th class="n">Scenario</th><th class="n">Change</th></tr>
      ${row("Generated (t)", B.generated_t, X.generated_t, "", true)}${row("Sold / dispatched (t)", B.sold_t, X.sold_t, "", true)}${row("Extra recovered in-plant (t)", B.extra_recovered_t, X.extra_recovered_t, "", true)}
      ${row("Unmanaged (t)", B.unmanaged_t, X.unmanaged_t, "", false)}${row("Diversion rate", B.diversion_pct, X.diversion_pct, "%", true)}</table></div>
      <p class="note">Assumptions: ${d.assumptions.map(esc).join("; ")}.</p></div>`;
}

function viewDecisions() {
  const all = openActions(), pending = all.filter(a => !S.decisions[a.id]);
  return `<div class="split"><div class="stack"><div class="card"><div class="ct">Waiting for a decision (${pending.length})</div>${pending.map(actionCard).join("") || '<p class="empty">Everything has been handled.</p>'}</div></div>
    <div class="card"><div class="ct"><span>Decision log</span>${S.log.length ? '<button class="btn alt" id="clearLog">Clear</button>' : ""}</div>
      ${S.log.length ? `<table><tr><th>Time</th><th>Decision</th></tr>${S.log.map(e => `<tr><td class="num">${esc(e.time)}</td><td><b>${esc(e.decision)}</b> ${tag(e.priority)}<br><span class="small">${esc(e.text)}</span><br><span class="small muted">${esc(e.section)}</span></td></tr>`).join("")}</table>` :
      '<p class="empty">No decisions yet. Acknowledge or defer an action and it is recorded here with the time.</p>'}
      <p class="note">The log is kept in this browser window only.</p></div></div>`;
}

function graphSvg(g) {
  const cols = ["Plant", "ProcessUnit", "Stream", "Use"], W = 900, H = 330, byCol = cols.map(c => g.nodes.filter(n => n.type === c)), pos = {};
  byCol.forEach((arr, ci) => arr.forEach((n, i) => { pos[n.id] = {x:90 + ci * 240, y:(H / (arr.length + 1)) * (i + 1)}; }));
  const lines = g.facts.map(f => { const a = pos[f.from_id], b = pos[f.to_id]; if (!a || !b) return "";
    return `<line x1="${a.x + 80}" y1="${a.y}" x2="${b.x - 80}" y2="${b.y}" stroke="${f.relation === "HAS_UNIT" ? C.muted : f.relation === "PRODUCES" ? C.peach2 : C.ink}" stroke-width="${f.relation === "HAS_UNIT" ? 1.5 : 2.4}" marker-end="url(#ga)"><title>${esc(f.from)} ${esc(f.relation)} ${esc(f.to)}${f.quantity_t ? " (" + int(f.quantity_t) + " t)" : ""}</title></line>`; }).join("");
  const labels = ["Plant", "Process units", "By-product streams", "Uses"].map((t, i) => `<text x="${90 + i * 240}" y="16" text-anchor="middle" class="ax">${t}</text>`).join("");
  const nodes = g.nodes.map(n => { const p = pos[n.id]; return `<g><rect x="${p.x - 80}" y="${p.y - 18}" width="160" height="36" rx="9" fill="${n.type === "Stream" ? C.peach : n.type === "Use" ? "#fff" : C.ink}" stroke="${C.ink}"/>
    <text x="${p.x}" y="${p.y + 5}" text-anchor="middle" font-size="12.5" font-weight="600" fill="${n.type === "Stream" || n.type === "Use" ? C.ink : C.peach4}">${esc(n.name)}</text></g>`; }).join("");
  return `<div class="flowwrap"><svg viewBox="0 0 ${W} ${H}" style="width:100%;min-width:700px" role="img" aria-label="Knowledge graph"><defs><marker id="ga" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10z" fill="${C.ink}"/></marker></defs>${labels}${lines}${nodes}</svg></div>`;
}
async function viewRecords() {
  const g = S.graph || (S.graph = await api("/api/graph")), facts = g.facts.filter(f => f.basis);
  return `<div class="stack">
    <div class="card"><div class="ct">Data sources</div><table>
      <tr><td><b>By-product tonnes</b></td><td>Tata Steel Jamshedpur, Form V (environmental statement), FY2021-22: slag generated, recycled and sold. Annual figures as filed.</td></tr>
      <tr><td><b>Energy readings</b></td><td>Open UCI "Steel Industry Energy Consumption" dataset, 2018, 15-minute readings. Replayed in sequence to show the forecast working.</td></tr>
      <tr><td><b>Generation factors</b></td><td>Indian Minerals Yearbook 2018 (BF slag 300-540 kg per tonne of pig iron; steel slag 150-200 kg per tonne of liquid steel).</td></tr></table>
      <p class="note">The slag figures and the energy readings come from different plants, so the energy data says nothing about the slag data. Values are replayed from datasets, not read live from a plant. This console only advises.</p></div>
    <div class="card"><div class="ct">Knowledge graph</div>${graphSvg(g)}<p class="note">Each fact below is an edge in this graph. Hover a line for its details.</p></div>
    <div class="card"><div class="ct">Facts (${facts.length})</div><div class="scroll"><table>
      <tr><th>From</th><th>Relation</th><th>To</th><th class="n">Tonnes</th><th>Basis</th><th>Source</th></tr>
      ${facts.map(f => `<tr><td>${esc(f.from)}</td><td>${esc(f.relation)}</td><td>${esc(f.to)}</td><td class="n">${f.quantity_t == null ? "-" : int(f.quantity_t)}</td><td>${tag(f.basis)}</td>
        <td>${esc(f.source)}${f.page == null ? ' <span class="small muted">(page not recorded)</span>' : ", p." + esc(f.page)}</td></tr>`).join("")}</table></div>
      <p class="note">${tag("OBSERVED")} read from a document &nbsp; ${tag("DERIVED")} calculated from other facts &nbsp; ${tag("ASSUMED")} an assumption, not a measurement.</p></div></div>`;
}

async function renderView() {
  let html = "";
  try {
    if (S.view === "overview") html = viewOverview();
    else if (S.view === "flow") html = await viewFlow();
    else if (S.view === "energy") html = await viewEnergy();
    else if (S.view === "lab") html = viewLab();
    else if (S.view === "decisions") html = viewDecisions();
    else if (S.view === "records") html = await viewRecords();
    else html = await viewSection(S.view);
  } catch (e) { return fail(e); }
  const keep = window.scrollY, changed = S.lastView !== S.view;
  $("view").innerHTML = html; S.lastView = S.view;
  drawCharts();
  if (S.view === "lab") bindLab();
  const an = $("anim"); if (an) an.onchange = () => { S.noanim = !an.checked; renderView(); };
  window.scrollTo(0, changed ? 0 : keep);
}
function setTitle() { const t = TITLES[S.view] || TITLES.overview; $("ptitle").textContent = t[0]; $("psub").textContent = t[1]; document.title = t[0] + " | CircuLoop"; }

/* ------------------------------------------------------------ interactions */
function go(view) { if (location.hash.slice(1) === view) route(); else location.hash = view; }
function route() {
  const v = location.hash.slice(1); S.view = TITLES[v] ? v : "overview"; setTitle(); renderNav(); renderView();
}
window.addEventListener("hashchange", route);

function bindLab() {
  const L = S.lab; let t;
  const upd = () => { L.gen = +$("s-gen").value; L.buy = +$("s-buy").value; L.rec = +$("s-rec").value;
    $("o-gen").textContent = L.gen + "%"; $("o-buy").textContent = L.buy + "%"; $("o-rec").textContent = L.rec + "%";
    clearTimeout(t); t = setTimeout(() => runLab().catch(fail), 90); };
  ["s-gen", "s-buy", "s-rec"].forEach(i => $(i).addEventListener("input", upd));
  $("labReset").onclick = () => { L.gen = L.buy = L.rec = 0; renderView(); };
  runLab().catch(fail);
}

document.addEventListener("click", ev => {
  const t = ev.target.closest("[data-view],[data-flow],[data-lab],[data-act],#clearLog,.node"); if (!t) return;
  if (t.dataset.act) {
    const a = ACTS[t.dataset.act]; if (!a) return;
    S.decisions[a.id] = t.dataset.dec;
    S.log.unshift({decision:t.dataset.dec, text:a.text, section:a.section || "", priority:a.priority, time:new Date().toLocaleTimeString("en-IN", {hour:"2-digit", minute:"2-digit"})});
    renderBand(); renderView(); return;
  }
  if (t.id === "clearLog") { S.log = []; renderView(); return; }
  if (t.dataset.lab) { S.lab.sid = t.dataset.lab; if (S.view === "lab") { renderView(); } else go("lab"); return; }
  if (t.dataset.flow || t.classList.contains("node")) { S.flowSel = t.dataset.flow; renderView(); return; }
  if (t.dataset.view) go(t.dataset.view);
});
document.addEventListener("keydown", ev => { if ((ev.key === "Enter" || ev.key === " ") && ev.target.classList && ev.target.classList.contains("node")) { ev.preventDefault(); S.flowSel = ev.target.dataset.flow; renderView(); } });

async function loadReading(i) {
  S.idx = Math.max(0, Math.min(S.max - 1, i)); S.busy = true;
  try {
    const [ser, exp] = await Promise.all([api(`/api/series?end=${S.idx}&n=96`), api(`/api/explain/${S.idx}`)]);
    S.ser = ser; S.exp = exp;
    $("whenTime").textContent = exp.time.slice(0, 16); $("whenIdx").textContent = `Reading ${int(S.idx)} of ${int(S.max)}`; $("slider").value = S.idx;
    renderBand();
    if (S.view === "overview" || S.view === "energy") await renderView();
  } finally { S.busy = false; }
}
function setPlaying(on) {
  S.playing = on; $("play").textContent = on ? "Pause" : "Play"; clearInterval(S.timer);
  if (on) S.timer = setInterval(() => { if (!S.busy) loadReading(S.idx + 1).catch(() => {}); }, 3500);
}
$("prev").onclick = () => { setPlaying(false); loadReading(S.idx - 1).catch(fail); };
$("next").onclick = () => { setPlaying(false); loadReading(S.idx + 1).catch(fail); };
$("play").onclick = () => setPlaying(!S.playing);
$("slider").oninput = e => { setPlaying(false); loadReading(+e.target.value).catch(fail); };
let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(drawCharts, 150); });

/* -------------------------------------------------------------------- chat */
function addMsg(who, text, extra) {
  S.chat.push({who, text, extra});
  $("msgs").innerHTML = S.chat.map(m => `<div class="m ${m.who}">${esc(m.text)}${m.extra ? `<small>${esc(m.extra)}</small>` : ""}</div>`).join("");
  $("msgs").scrollTop = $("msgs").scrollHeight;
}
function setChips(list) { $("chips").innerHTML = list.map(q => `<button class="chip" type="button">${esc(q)}</button>`).join(""); }
async function ask(q) {
  q = q.trim(); if (!q) return;
  addMsg("me", q); $("chatIn").value = "";
  try { const r = await api("/api/chat", {message:q, index:S.idx}); addMsg("bot", r.answer, r.intent ? "Topic: " + r.intent.replace("_", " ") : ""); setChips(r.suggestions); }
  catch (e) { addMsg("bot", "I could not reach the server. Check that it is running."); }
}
$("chatFab").onclick = () => { $("chat").hidden = false; $("chatIn").focus();
  if (!S.chat.length) { addMsg("bot", "Hello. I answer from the values on this dashboard: the energy forecast, the slag records, circularity figures, recommended actions and what-if changes. I am a question-matching assistant, not a general chatbot."); setChips(["Give me a summary", "What should I do?", "Why is LD slag flagged?", "What if we lose 30% of buyers?"]); } };
$("chatClose").onclick = () => { $("chat").hidden = true; };
$("chatForm").onsubmit = e => { e.preventDefault(); ask($("chatIn").value); };
$("chips").onclick = e => { const c = e.target.closest(".chip"); if (c) ask(c.textContent); };
document.addEventListener("keydown", e => { if (e.key === "Escape") $("chat").hidden = true; });

/* ------------------------------------------------------------------- start */
(async function start() {
  try {
    S.ov = await api("/api/overview"); S.hourly = await api("/api/hourly");
    S.max = S.ov.readings; $("slider").max = S.max - 1;
    await loadReading(S.idx);
    route();
    setPlaying(true);
  } catch (e) { fail(e); }
})();
