// Records two takes of the running Gatekeeper app (http://127.0.0.1:8765) and cuts them to exact lengths.
// Run from the repo root: node video/capture.mjs
import { chromium } from "/opt/homebrew/lib/node_modules/playwright/index.mjs";
import { execFileSync } from "node:child_process";
import { mkdirSync, renameSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const OUT = join(ROOT, "out");
const URL = "http://127.0.0.1:8765/";
for (const d of ["raw", "seg", "stills", "debug"]) mkdirSync(join(OUT, d), { recursive: true });

// Playwright videos have no pointer, so a drawn one follows the real mousemove events.
const CURSOR = `addEventListener("DOMContentLoaded", () => {
  const c = document.createElement("div");
  c.innerHTML = '<svg width="22" height="30" viewBox="0 0 22 30"><path d="M2 2 L2 24 L8 18 L12 28 L16 26 L12 17 L20 17 Z" fill="#16202A" stroke="#fff" stroke-width="1.5"/></svg>';
  Object.assign(c.style, { position: "fixed", left: "-40px", top: "-40px", zIndex: 99999, pointerEvents: "none" });
  document.body.append(c);
  addEventListener("mousemove", (e) => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
});`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function glide(page, sel, dx = 0, dy = 0) {
  const box = await page.locator(sel).first().boundingBox();
  if (!box) { await page.screenshot({ path: join(OUT, "debug", `missing-${sel.replace(/\W+/g, "_")}.png`) }); throw new Error(`no box for ${sel}`); }
  await page.mouse.move(box.x + box.width / 2 + dx, box.y + box.height / 2 + dy, { steps: 15 });
}

async function wheel(page, total, step = 80, pause = 180) {
  for (let done = 0; Math.abs(done) < Math.abs(total); done += step) {
    await page.mouse.wheel(0, step);
    await sleep(pause);
  }
}

async function take(name, story) {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
    recordVideo: { dir: join(OUT, "raw"), size: { width: 1920, height: 1080 } },
  });
  await context.addInitScript(CURSOR);
  const page = await context.newPage();
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  const t0 = Date.now();
  const marks = await story(page);
  const total = (Date.now() - t0) / 1000;
  await context.close();
  await browser.close();
  const webm = join(OUT, "raw", `${name}.webm`);
  renameSync(await page.video().path(), webm);
  return { webm, total, marks };
}

function probe(file) {
  const out = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration", "-of", "default=nw=1", file]).toString();
  return out.trim().replace(/\n/g, " ");
}

function encode(webm, out, start, dur) {
  // Input seeking (-ss before -i): output seeking on these VP8 webms turns black after 15 s of input.
  const vf = `scale=1920:1080:flags=lanczos,fade=t=in:st=0:d=0.4,fade=t=out:st=${(dur - 0.4).toFixed(3)}:d=0.4,tpad=stop_mode=clone:stop_duration=2`;
  execFileSync("ffmpeg", ["-y", "-v", "error", "-ss", start.toFixed(3), "-i", webm, "-t", String(dur), "-r", "30", "-vf", vf,
    "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "18", "-t", String(dur), out]);
  console.log(out, probe(out));
}

async function submit(page, id, cls) {
  await glide(page, "#example");
  await page.selectOption("#example", id);
  await sleep(500);
  return cls;
}

async function decide(page, cls, still) {
  await glide(page, "#submit");
  await sleep(300);
  await page.click("#submit");
  await page.waitForSelector(`#notice-slot .notice.${cls}`);
  await sleep(1200);
  await page.locator("#notice-slot .notice").screenshot({ path: join(OUT, "stills", still) });
}

// Take 1: applicant submits R05 (APPROVE_SPE), then R02 (REJECT).
const applicant = await take("02-applicant", async (page) => {
  await page.mouse.move(900, 300, { steps: 20 });
  await glide(page, ".welcome-lead");
  await sleep(4200);
  await submit(page, "R05");
  await glide(page, "textarea[name=purpose]", 0, -20);
  await sleep(800);
  await wheel(page, 240, 60, 400);
  await glide(page, "textarea[name=question]", 0, 10);
  await sleep(1500);
  await wheel(page, -240, -60, 400);
  await sleep(1000);
  await decide(page, "d-APPROVE_SPE", "02-approve-spe.png");
  await glide(page, "#notice-slot .verdict");
  await sleep(1200);
  await glide(page, "#notice-slot .sealed .big");
  await sleep(3200);
  await submit(page, "R02");
  await sleep(300);
  await decide(page, "d-REJECT", "02-reject.png");
  await glide(page, "#notice-slot .reasons .art");
  await sleep(1200);
  await glide(page, "#notice-slot .reasons p");
  await sleep(3400);
});
console.log("applicant take", applicant.total.toFixed(1), "s");

// Take 2: R05 submitted first (so its notice holds the download button), then the staff view.
const staff = await take("04-staff", async (page) => {
  await submit(page, "R05");
  await decide(page, "d-APPROVE_SPE", "04-r05-notice.png");
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(300);
  const marks = {};
  marks.staff = Date.now();
  await glide(page, '.view-btn[data-view="staff"]');
  await sleep(300);
  await page.click('.view-btn[data-view="staff"]');
  await page.waitForFunction(() => document.querySelectorAll("#hospital-list .hosp").length === 3);
  await glide(page, "#hospital-list");
  await sleep(500);
  await glide(page, "#run-samples");
  await sleep(300);
  await page.click("#run-samples");
  await page.waitForFunction(() => document.querySelector("#run-samples").textContent.startsWith("Deciding"));
  await page.waitForFunction(() => document.querySelector("#run-samples").textContent === "Decide the 10 sample requests", null, { timeout: 180000 });
  await page.waitForSelector('.case-row[data-id="R05"]');
  marks.queueDone = Date.now();
  await sleep(600);
  await glide(page, '.case-row[data-id="R05"]');
  await sleep(300);
  await page.click('.case-row[data-id="R05"]');
  await page.waitForSelector("#casefile .cf-head");
  await sleep(500);
  await glide(page, "#casefile details.sql:nth-of-type(2) summary, #casefile details.sql summary");
  await page.locator("#casefile details.sql summary").last().click();
  await sleep(400);
  await glide(page, "#casefile details.sql pre");
  await wheel(page, 720, 90, 120);
  await sleep(500);
  await page.locator("#casefile h3", { hasText: "Secure processing environment" }).scrollIntoViewIfNeeded();
  await glide(page, "#casefile .facts dd.code");
  await sleep(1000);
  marks.toApplicant = Date.now();
  await page.evaluate(() => window.scrollTo(0, 0));
  await glide(page, '.view-btn[data-view="applicant"]');
  await sleep(200);
  await page.click('.view-btn[data-view="applicant"]');
  await sleep(400);
  await page.locator("#notice-slot .dl-btn").scrollIntoViewIfNeeded();
  await glide(page, "#notice-slot .dl-btn");
  await sleep(500);
  await page.click("#notice-slot .dl-btn");
  await page.waitForFunction(() => document.querySelector("#notice-slot .dl-btn").textContent === "Download blocked");
  marks.blocked = Date.now();
  await sleep(600);
  await page.locator("#notice-slot .sealed").screenshot({ path: join(OUT, "stills", "04-download-blocked.png") });
  await sleep(2600);
  marks.end = Date.now();
  return marks;
});
const m = staff.marks;
console.log("staff take", staff.total.toFixed(1), "s; staff part", ((m.end - m.staff) / 1000).toFixed(1), "s; queue", ((m.queueDone - m.staff) / 1000).toFixed(1), "s; from applicant switch", ((m.end - m.toApplicant) / 1000).toFixed(1), "s");

const dur = (f) => parseFloat(probe(f).match(/duration=([\d.]+)/)[1]);
const d1 = dur(applicant.webm), d2 = dur(staff.webm);
console.log("raw", d1.toFixed(2), d2.toFixed(2));
encode(applicant.webm, join(OUT, "seg", "02-applicant.mp4"), Math.max(0, d1 - 25.2), 25);
encode(staff.webm, join(OUT, "seg", "04-staff.mp4"), Math.max(0, d2 - 15.2), 15);
