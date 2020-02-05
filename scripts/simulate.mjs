#!/usr/bin/env node
// Moves the mock boards forward in time and scrapes after every step, then
// scores the backend against the boards' ground truth (scripts/evaluate-dedupe.mjs).
//
//   node scripts/simulate.mjs [--steps 6] [--days 5]
//
// Needs the mock boards and the backend running (e.g. via scripts/dev.mjs).

import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { values } = parseArgs({
  options: {
    steps: { type: 'string', default: '6' },
    days: { type: 'string', default: '5' },
    boards: { type: 'string', default: process.env.BOARDS_URL ?? 'http://127.0.0.1:4010' },
  },
});
const env = { INGEST_TOKEN: 'dev-ingest-token', LOG_LEVEL: 'error', ...process.env };

function node(script, argv, cwd = ROOT) {
  const result = spawnSync(process.execPath, [script, ...argv], { cwd, env, encoding: 'utf8' });
  return { code: result.status, out: `${result.stdout}${result.stderr}`.trim() };
}

/** POST with retries: an idle keep-alive socket can be reset just as we reuse it. */
async function post(url, body) {
  for (let attempt = 1; ; attempt += 1) {
    try {
      return await (await fetch(url, { method: 'POST', body: JSON.stringify(body) })).json();
    } catch (err) {
      if (attempt >= 3) throw err;
    }
  }
}

const start = (await (await fetch(`${values.boards}/__admin/state`)).json()).day;
let failures = 0;
for (let step = 0; step <= Number(values.steps); step += 1) {
  if (step > 0) await post(`${values.boards}/__admin/tick`, { to: start + step * Number(values.days) });
  const scrape = node('src/cli.js', ['run'], path.join(ROOT, 'scrapers'));
  const lines = scrape.out.split('\n').filter((l) => /^(stackjobs|remotehub|citycareers) /.test(l));
  const evaluation = node(path.join('scripts', 'evaluate-dedupe.mjs'), ['--boards', values.boards]);
  const summary = evaluation.out.split('\n');
  console.log(`\n== ${summary[0]}`);
  for (const line of lines) console.log(`   ${line.replace(/\s+\{.*\}/, '')}`); // "stackjobs  ok  closed=7"
  for (const line of summary.slice(1)) console.log(`   ${line}`);
  if (evaluation.code !== 0 || scrape.code !== 0) failures += 1;
}
console.log(failures ? `\n${failures} step(s) did not match the ground truth` : '\nall steps matched the ground truth');
process.exitCode = failures ? 1 : 0;

function detectLanguage(data) {
  if (!data) return null;
  return data;
}