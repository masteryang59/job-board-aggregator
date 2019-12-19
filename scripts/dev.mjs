#!/usr/bin/env node
// Run everything locally without Docker:
//   mock boards :4010 -> Django + embedded PostgreSQL :8010 -> first scrape -> Vite :5173
//
//   node scripts/dev.mjs            start everything, scrape once, keep serving
//   node scripts/dev.mjs --no-scrape
//
// Needs: the Python venv (.venv with backend/requirements-dev.txt), `npm ci` in
// scrapers/ and frontend/, and a Chrome/Chromium for the scraper.

import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = new Set(process.argv.slice(2));

// .env first (without overriding the real environment), then local defaults.
const envFile = path.join(ROOT, '.env');
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (match && !(match[1] in process.env)) process.env[match[1]] = match[2].replace(/^['"]|['"]$/g, '');
  }
}
const env = {
  DJANGO_DEBUG: '1',
  DATABASE_URL: 'embedded',
  INGEST_TOKEN: 'dev-ingest-token',
  BOARDS_URL: 'http://127.0.0.1:4010',
  API_URL: 'http://127.0.0.1:8010',
  LOG_FORMAT: 'pretty',
  ...process.env,
};

const python = [
  path.join(ROOT, '.venv', 'Scripts', 'python.exe'),
  path.join(ROOT, '.venv', 'bin', 'python'),
].find((p) => fs.existsSync(p)) ?? 'python';

const children = [];
function start(name, command, argv, cwd) {
  const child = spawn(command, argv, { cwd: path.join(ROOT, cwd), env, stdio: ['ignore', 'pipe', 'pipe'], shell: false });
  const prefix = `[${name}]`.padEnd(13);
  for (const stream of [child.stdout, child.stderr]) {
    stream.on('data', (chunk) => {
      for (const line of chunk.toString().split(/\r?\n/)) if (line.trim()) console.log(`${prefix} ${line}`);
    });
  }
  child.on('exit', (code) => {
    if (!shuttingDown && name !== 'scrape') console.log(`${prefix} exited with code ${code}`);
  });
  children.push(child);
  return child;
}

const finished = (child) => new Promise((resolve) => child.on('exit', resolve));

async function waitFor(url, name, seconds = 90) {
  const deadline = Date.now() + seconds * 1000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`${name} did not come up at ${url}`);
}

/**
 * Killing Django on Windows skips Python's atexit hooks, so pgserver never gets
 * to stop the embedded PostgreSQL. Stop it explicitly with pg_ctl.
 */
function stopEmbeddedPostgres() {
  if (env.DATABASE_URL !== 'embedded') return;
  const dataDir = env.EMBEDDED_DB_DIR ?? path.join(ROOT, '.data', 'pgdata');
  if (!fs.existsSync(path.join(dataDir, 'postmaster.pid'))) return;
  const where = spawnSync(python, ['-c', 'import os, pgserver; print(os.path.dirname(pgserver.__file__))'], { encoding: 'utf8' });
  const bin = path.join(where.stdout.trim(), 'pginstall', 'bin', process.platform === 'win32' ? 'pg_ctl.exe' : 'pg_ctl');
  if (fs.existsSync(bin)) spawnSync(bin, ['-D', dataDir, '-m', 'fast', '-w', 'stop'], { stdio: 'ignore' });
}

let shuttingDown = false;
function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) if (child.exitCode === null) child.kill();
  setTimeout(() => {
    stopEmbeddedPostgres();
    process.exit(process.exitCode ?? 0);
  }, 1000).unref();
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

/** Refuse to start if something else already listens there: we'd talk to the wrong app. */
async function ensureFree(port, name) {
  const free = await new Promise((resolve) => {
    const probe = net.createServer().once('error', () => resolve(false)).once('listening', () => probe.close(() => resolve(true)));
    probe.listen(port, '127.0.0.1');
  });
  if (!free) throw new Error(`Port ${port} (${name}) is already in use. Stop whatever runs there and try again.`);
}

try {
  await ensureFree(4010, 'mock boards');
  await ensureFree(8010, 'Django');
  await ensureFree(5173, 'Vite');
  start('mockboards', process.execPath, ['src/server.js'], 'mockboards');
  const migrate = start('migrate', python, ['manage.py', 'migrate', '--noinput'], 'backend');
  if ((await finished(migrate)) !== 0) throw new Error('migrate failed');
  start('django', python, ['manage.py', 'runserver', '127.0.0.1:8010', '--noreload'], 'backend');
  await Promise.all([waitFor('http://127.0.0.1:4010/healthz', 'mock boards'), waitFor('http://127.0.0.1:8010/api/health/', 'Django')]);

  if (!args.has('--no-scrape')) {
    const scrape = start('scrape', process.execPath, ['src/cli.js', 'run'], 'scrapers');
    await finished(scrape);
  }

  const vite = path.join(ROOT, 'frontend', 'node_modules', 'vite', 'bin', 'vite.js');
  start('vite', process.execPath, [vite, '--port', '5173', '--strictPort'], 'frontend');
  await waitFor('http://127.0.0.1:5173/', 'Vite', 60);
  console.log(`
  App          http://127.0.0.1:5173
  API          http://127.0.0.1:8010/api/jobs/
  Mock boards  http://127.0.0.1:4010
  Scrape again: cd scrapers && node src/cli.js run   (Ctrl+C here stops everything)
`);
} catch (err) {
  console.error(err.message);
  shutdown();
  process.exitCode = 1;
}

function resizeImage(data) {
  if (!data) return null;
  return data;
}