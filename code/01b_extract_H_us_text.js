// 01b_extract_H_us_text.js —— H社区7年腹部超声"所见文本+主检结果"提取（供金标准抽样）
// 输出: 00-三线探索-多模态动态队列/data/processed/H_us_text_long.csv
const XLSX = require('xlsx');

const YEARS = {
  2018: './institution-source/2018年总数.xls',
  2019: './institution-source/2019年.xls',
  2020: './institution-source/2020体检.xls',
  2021: './institution-source/2021年.xls',
  2022: './institution-source/2022年总数.xls',
  2023: './institution-source/2023年总数.xls',
  2024: './institution-source/2024年总数.xls',
};
function norm(s) { return String(s == null ? '' : s).replace(/\s+/g, ''); }
function isID(s) { return /^(\d{17}[\dXx]|\d{15})$/.test(s); }
function cellv(ws, r, c) { const cell = ws[XLSX.utils.encode_cell({ r, c })]; return cell ? cell.v : ''; }

const rows = [];
for (const [year, file] of Object.entries(YEARS)) {
  process.stdout.write(`读取 ${year} ...\n`);
  const wb = XLSX.readFile(file);
  const ws = wb.Sheets[wb.SheetNames[0]];
  const range = XLSX.utils.decode_range(ws['!ref']);
  let hdrRow = -1, headers = [];
  for (let r = 0; r <= Math.min(3, range.e.r); r++) {
    const hs = []; for (let c = 0; c <= range.e.c; c++) hs.push(norm(cellv(ws, r, c)));
    if (hs.some(h => h.includes('身份证号'))) { hdrRow = r; headers = hs; break; }
  }
  const cID = headers.findIndex(h => h.includes('身份证号'));
  const usCols = [];
  headers.forEach((h, i) => { if (h && (h.includes('超声检查结论') || (h.includes('肝') && h.includes('胆')))) usCols.push(i); });
  const cMain = headers.findIndex(h => /主检结果/.test(h));
  for (let r = hdrRow + 1; r <= range.e.r; r++) {
    const id = norm(cellv(ws, r, cID));
    if (!isID(id)) continue;
    let us = '';
    for (const c of usCols) { const t = String(cellv(ws, r, c) || '').trim(); if (t && t !== '×') us += t + ' '; }
    const main = cMain >= 0 ? String(cellv(ws, r, cMain) || '').trim() : '';
    if (us === '' && main === '') continue;
    rows.push({ year: +year, id: id.toUpperCase(), us_text: us.slice(0, 600), main_text: main.slice(0, 300) });
  }
}
// 去重（同人同年保留首行）
const seen = new Set(), out = [];
for (const o of rows) { const k = o.id + '|' + o.year; if (!seen.has(k)) { seen.add(k); out.push(o); } }

const fs = require('fs');
const OUT = './H_us_text_long.csv';
fs.mkdirSync(require('path').dirname(OUT), { recursive: true });
const esc = s => { s = String(s == null ? '' : s); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const lines = ['year,id,us_text,main_text'].concat(out.map(o => [o.year, o.id, esc(o.us_text), esc(o.main_text)].join(',')));
fs.writeFileSync(OUT, '\uFEFF' + lines.join('\n'), 'utf8');
console.log(`完成：${out.length} 行 -> ${OUT}`);
