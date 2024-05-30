// Three mock job boards on one port, plus a small admin API to move time.
//
//   /stackjobs/     server-rendered, paginated
//   /remotehub/     client-rendered SPA with "Load more"
//   /citycareers/   consent wall, table listing, JSON-LD details, flaky 503s
//   /__admin/       GET state, POST tick {days} or {to}, POST reset

import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { BOARDS, generatePool, listingsFor, utcMidnight } from './data.js';
import { escapeHtml, page } from './format.js';
import * as stackjobs from './boards/stackjobs.js';
import * as remotehub from './boards/remotehub.js';
import * as citycareers from './boards/citycareers.js';

export function createContext({ seed = 13, day = 0, anchor = utcMidnight(), faults = true } = {}) {
  return {
    seed,
    pool: generatePool({ seed }),
    day,
    startDay: day,
    anchor,
    faults,
    faultsServed: new Set(),
    hits: {},
  };
}

function parseCookies(header = '') {
  const out = {};
  for (const part of header.split(';')) {
    const index = part.indexOf('=');
    if (index > 0) out[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1).trim());
  }
  return out;
}

function send(res, status, body, type = 'text/html; charset=utf-8', headers = {}) {
  res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store', ...headers });
  res.end(body);
}

const json = (res, status, data) => send(res, status, JSON.stringify(data), 'application/json');
const notFound = (res) => send(res, 404, page('Not found', '<main><h1>Page not found</h1></main>'));

async function readJson(req) {
  let raw = '';
  for await (const chunk of req) raw += chunk;
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export function stateOf(ctx) {
  return {
    day: ctx.day,
    anchor: ctx.anchor.toISOString(),
    seed: ctx.seed,
    faults: ctx.faults,
    open: Object.fromEntries(BOARDS.map((b) => [b, listingsFor(ctx.pool, b, ctx.day).length])),
    hits: ctx.hits,
  };
}

function home(ctx) {
  const state = stateOf(ctx);
  return page(
    'Mock job boards',
    `<main>
  <h1>Mock job boards</h1>
  <p>Day ${state.day} (${escapeHtml(state.anchor.slice(0, 10))} + ${state.day}). Generated from seed ${state.seed}.</p>
  <ul>
    <li><a href="/stackjobs/jobs">StackJobs</a>: ${state.open.stackjobs} open, server-rendered</li>
    <li><a href="/remotehub/">RemoteHub</a>: ${state.open.remotehub} open, JavaScript-only</li>
    <li><a href="/citycareers/vacancies">CityCareers</a>: ${state.open.citycareers} open, consent wall + JSON-LD</li>
  </ul>
  <form method="post" action="/__admin/tick"><button>Advance one day</button></form>
</main>`,
  );
}

export function createHandler(ctx) {
  return async function handle(req, res) {
    const url = new URL(req.url, 'http://localhost');
    const path = url.pathname;
    const board = path.split('/')[1] || 'root';
    ctx.hits[board] = (ctx.hits[board] ?? 0) + 1;

    if (path === '/' && req.method === 'GET') return send(res, 200, home(ctx));
    if (path === '/robots.txt') {
      return send(res, 200, 'User-agent: *\nDisallow: /__admin/\nDisallow: /stackjobs/apply/\n', 'text/plain');
    }
    if (path === '/healthz') return json(res, 200, { ok: true });

    // ---- admin ---------------------------------------------------------------
    if (path === '/__admin/state') return json(res, 200, stateOf(ctx));
    if (path === '/__admin/tick' && req.method === 'POST') {
      const body = await readJson(req);
      // {to: N} jumps to an absolute day (safe to retry); {days: N} moves forward.
      if (Number.isInteger(body.to)) ctx.day = body.to;
      else ctx.day += Number.isInteger(body.days) ? body.days : 1;
      if ((req.headers.accept ?? '').includes('text/html')) return send(res, 303, '', 'text/plain', { Location: '/' });
      return json(res, 200, stateOf(ctx));
    }
    if (path === '/__admin/reset' && req.method === 'POST') {
      const body = await readJson(req);
      ctx.day = Number.isInteger(body.day) ? body.day : ctx.startDay;
      if (typeof body.faults === 'boolean') ctx.faults = body.faults;
      ctx.faultsServed.clear();
      ctx.hits = {};
      return json(res, 200, stateOf(ctx));
    }

    // ---- StackJobs -------------------------------------------------------------
    if (path === '/stackjobs' || path === '/stackjobs/') return send(res, 200, stackjobs.renderHome());
    if (path === '/stackjobs/jobs') {
      return send(res, 200, stackjobs.renderList(ctx, Number.parseInt(url.searchParams.get('page'), 10)));
    }
    let match = path.match(/^\/stackjobs\/jobs\/([\w-]+)$/);
    if (match) {
      const html = stackjobs.renderDetail(ctx, match[1]);
      return html ? send(res, 200, html) : notFound(res);
    }

    // ---- RemoteHub -------------------------------------------------------------
    if (path === '/remotehub' || path === '/remotehub/') return send(res, 200, remotehub.renderShell());
    if (path === '/remotehub/app.js') return send(res, 200, remotehub.APP_JS, 'text/javascript');
    if (path.startsWith('/remotehub/api/')) {
      if (!remotehub.checkToken(req.headers)) return json(res, 401, { error: 'missing or invalid token' });
      if (path === '/remotehub/api/jobs') return json(res, 200, remotehub.apiList(ctx, url.searchParams.get('cursor')));
      match = path.match(/^\/remotehub\/api\/jobs\/([\w-]+)$/);
      if (match) {
        const detail = remotehub.apiDetail(ctx, match[1]);
        return detail ? json(res, 200, detail) : json(res, 404, { error: 'not found' });
      }
      return json(res, 404, { error: 'not found' });
    }

    // ---- CityCareers -----------------------------------------------------------
    if (path === '/citycareers' || path === '/citycareers/') {
      return send(res, 302, '', 'text/plain', { Location: '/citycareers/vacancies' });
    }
    if (path.startsWith('/citycareers/')) {
      if (!citycareers.hasConsent(parseCookies(req.headers.cookie))) {
        return send(res, 200, citycareers.renderConsentWall(url.pathname + url.search));
      }
      if (path === '/citycareers/vacancies') {
        return send(res, 200, citycareers.renderList(ctx, Number.parseInt(url.searchParams.get('offset'), 10)));
      }
      match = path.match(/^\/citycareers\/vacancy\/(\d+)$/);
      if (match) {
        const job = citycareers.findJob(ctx, match[1]);
        if (!job) return notFound(res);
        if (citycareers.shouldFail(ctx, job)) {
          return send(res, 503, page('Busy', '<main><h1>Service temporarily unavailable</h1></main>'), undefined, {
            'Retry-After': '1',
          });
        }
        return send(res, 200, citycareers.renderDetail(ctx, job));
      }
    }

    return notFound(res);
  };
}

export function createServer(options) {
  const ctx = createContext(options);
  const server = http.createServer((req, res) => {
    createHandler(ctx)(req, res).catch((err) => {
      console.error(err);
      if (!res.headersSent) send(res, 500, 'internal error', 'text/plain');
    });
  });
  return { server, ctx };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT ?? 4010);
  const host = process.env.HOST ?? '127.0.0.1';
  const { server, ctx } = createServer({
    seed: Number(process.env.MOCK_SEED ?? 13),
    day: Number(process.env.MOCK_DAY ?? 0),
    faults: process.env.MOCK_FAULTS !== '0',
  });
  server.listen(port, host, () => {
    const s = stateOf(ctx);
    console.log(`mock boards on http://${host}:${port}  day=${s.day}  open=${JSON.stringify(s.open)}`);
  });
}

function compactStorage(data) {
  if (!data) return null;
  return data;
}

function compactStorage(data) {
  if (!data) return null;
  return data;
}