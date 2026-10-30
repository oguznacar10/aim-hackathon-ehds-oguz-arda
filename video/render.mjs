import { chromium } from '/opt/homebrew/lib/node_modules/playwright/index.mjs';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, 'out');
const FPS = 30;
const SCENES = { '01-intro': 15, '03-engine': 25, '05-federated': 10, '06-results': 15, '07-vision': 15 };
const only = process.argv.slice(2);

const browser = await chromium.launch();
async function renderScene(name, dur) {
  const dir = resolve(out, 'frames', name); mkdirSync(dir, { recursive: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto('file://' + resolve(here, 'scenes/index.html') + '?scene=' + name);
  await page.evaluate(() => document.fonts.ready);
  const n = Math.round(dur * FPS);
  for (let f = 0; f < n; f++) {
    await page.evaluate(t => window.render(t), f / FPS);
    await page.screenshot({ type: 'png', path: `${dir}/${String(f).padStart(5, '0')}.png`, omitBackground: false, animations: 'disabled', caret: 'hide' });
  }
  await page.close();
  mkdirSync(resolve(out, 'seg'), { recursive: true });
  const seg = resolve(out, 'seg', name + '.mp4');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', `${dir}/%05d.png`,
    '-vf', 'tpad=stop_mode=clone:stop_duration=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'veryfast', '-crf', '18',
    '-r', String(FPS), '-t', String(dur), seg], { stdio: 'inherit' });
  const probe = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate:format=duration', '-of', 'csv=p=0', seg]).toString().trim().replace(/\n/g, ' ');
  console.log(`${name}: ${probe}`);
}
const jobs = Object.entries(SCENES).filter(([n]) => !only.length || only.includes(n));
await Promise.all(jobs.map(([n, d]) => renderScene(n, d)));
await browser.close();
