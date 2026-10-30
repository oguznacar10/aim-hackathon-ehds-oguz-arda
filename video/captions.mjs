// Splits narration.txt into caption cues, renders each to out/captions/cue-NN.png, writes out/captions/cues.json.
import { chromium } from '/opt/homebrew/lib/node_modules/playwright/index.mjs';
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, 'out', 'captions');
mkdirSync(outDir, { recursive: true });

const starts = [0, 15, 40, 65, 90, 105], ends = [15, 40, 65, 90, 105, 120];
const script = readFileSync(join(here, 'narration.txt'), 'utf8');
const segments = [...script.matchAll(/^\[(\d)\] \S+\n([\s\S]*?)(?=\n\n|\n*$)/gm)].map(m => m[2].trim());
assert.equal(segments.length, 6, 'narration.txt must hold six [N] blocks');

const words = s => s.split(/\s+/).filter(Boolean).length;
// Chunks end at punctuation so cue boundaries fall on clause boundaries; a comma inside a number does not split.
const chunk = text => text.match(/[^]+?[.,:;](?=\s|$)|[^]+$/g).map(s => s.trim()).filter(Boolean);
const TWO_LINES = 36 + 2 * 52; // padding plus two lines at 40 px * 1.3

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto('file://' + join(here, 'captions', 'index.html'));
const show = async text => {
  await page.evaluate(t => { document.getElementById('cue').textContent = t; }, text);
  await page.evaluate(() => document.fonts.ready);
  return page.evaluate(() => document.getElementById('cue').getBoundingClientRect().height);
};

const cues = [];
for (const [si, text] of segments.entries()) {
  const groups = [];
  let cur = [];
  for (const c of chunk(text)) {
    // The browser wraps at 1500 px, so a cue closes when the next chunk would need a third line or starts a new sentence after a full-length cue.
    const full = cur.length && (await show([...cur, c].join(' ')) > TWO_LINES + 1 || (/\.$/.test(cur.at(-1)) && words(cur.join(' ')) >= 8));
    if (full) { groups.push(cur); cur = []; }
    cur.push(c);
  }
  if (cur.length) groups.push(cur);
  const total = words(text), s = starts[si], e = ends[si];
  let acc = 0, prevEnd = s;
  for (const g of groups) {
    acc += words(g.join(' '));
    const end = acc === total ? e : Number((s + (e - s) * acc / total).toFixed(3));
    cues.push({ start: prevEnd, end, text: g.join(' ') });
    prevEnd = end;
  }
}

for (const [i, c] of cues.entries()) {
  c.file = `cue-${String(i + 1).padStart(2, '0')}.png`;
  assert.ok(c.end <= 120 && c.start < c.end && (i === 0 || c.start >= cues[i - 1].end), `cue ${i + 1} timing`);
  assert.ok(!c.text.includes(String.fromCharCode(8212)), 'em-dash in cue');
  const h = await show(c.text);
  assert.ok(h <= TWO_LINES + 1, `${c.file} wraps past 2 lines (${h}px)`);
  await page.screenshot({ path: join(outDir, c.file), omitBackground: true, type: 'png' });
}
await browser.close();

const out = cues.map(({ file, start, end, text }) => ({ file, start, end, text }));
writeFileSync(join(outDir, 'cues.json'), JSON.stringify(out, null, 2) + '\n');
const pngs = readdirSync(outDir).filter(f => /^cue-\d+\.png$/.test(f)).length;
assert.equal(pngs, out.length, 'png count != cue count');
console.log(`${out.length} cues, ${pngs} PNGs`);
console.log('first:', JSON.stringify(out[0]));
console.log('last: ', JSON.stringify(out.at(-1)));
