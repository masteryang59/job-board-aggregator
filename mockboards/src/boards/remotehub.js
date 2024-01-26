// RemoteHub: a client-rendered single-page app. The HTML shell is empty; cards
// are rendered by JavaScript after a token-protected API call, more cards load
// with a "Load more" button, and job details render on a hash route. Plain HTTP
// scraping sees nothing, which is why this source needs a real browser.

import crypto from 'node:crypto';
import { page } from '../format.js';
import { dateForDay, listingsFor, postedDay } from '../data.js';

export const PAGE_SIZE = 12;

export const externalId = (job) => `rh_${(job.id * 7919).toString(36)}`;

const KINDS = { full_time: 'Full Time', part_time: 'Part Time', contract: 'Contract', internship: 'Internship' };

// "120k–150k USD", "65–80 USD/hr", "2.1k EUR/mo"
function compText(salary) {
  if (!salary) return null;
  const k = (n) => (n >= 1000 ? `${Number((n / 1000).toFixed(1))}k` : String(n));
  const range = salary.min === salary.max ? k(salary.min) : `${k(salary.min)}–${k(salary.max)}`;
  const unit = { year: '', month: '/mo', hour: '/hr' }[salary.period];
  return `${range} ${salary.currency}${unit}`;
}

/** A per-process token the shell embeds; the API rejects calls without it. */
export const SESSION_TOKEN = crypto.randomBytes(12).toString('hex');

function toItem(ctx, job) {
  return {
    id: externalId(job),
    position: job.title,
    org: job.company,
    region: job.remoteRegion === 'Worldwide' ? 'Remote — Worldwide' : `Remote (${job.remoteRegion} only)`,
    comp: compText(job.salary),
    kind: KINDS[job.employmentType],
    skills: job.skills,
    published: dateForDay(ctx.anchor, postedDay(job, 'remotehub')).getTime() + 9 * 3_600_000,
  };
}

export function apiList(ctx, cursor) {
  const jobs = listingsFor(ctx.pool, 'remotehub', ctx.day);
  const start = Math.max(0, Number.parseInt(cursor, 10) || 0);
  const items = jobs.slice(start, start + PAGE_SIZE).map((job) => toItem(ctx, job));
  const next = start + PAGE_SIZE < jobs.length ? start + PAGE_SIZE : null;
  return { total: jobs.length, items, next };
}

export function apiDetail(ctx, id) {
  const job = listingsFor(ctx.pool, 'remotehub', ctx.day).find((j) => externalId(j) === id);
  if (!job) return null;
  return { ...toItem(ctx, job), body_html: job.description };
}

const CSS = `
  header { background: #0f766e; color: #fff; padding: 14px 16px; font-weight: 700; }
  .rh-card { display: block; background: #fff; border-radius: 10px; padding: 14px 16px; margin: 12px 0; cursor: pointer; text-decoration: none; }
  .rh-card__title { font-weight: 700; }
  .rh-card__org, .rh-card__region, time { color: #4b5563; font-size: .9rem; }
  .rh-chip { display: inline-block; background: #ccfbf1; border-radius: 99px; padding: 1px 8px; margin-right: 4px; font-size: .8rem; }
  #load-more { display: block; margin: 16px auto; padding: 8px 16px; }
  .rh-loading { color: #6b7280; }
`;

export function renderShell() {
  return page(
    'RemoteHub – remote jobs',
    `<header>RemoteHub</header>
<main><div id="app"><p class="rh-loading">Loading…</p></div></main>
<script>window.__RH_TOKEN__ = ${JSON.stringify(SESSION_TOKEN)};</script>
<script src="/remotehub/app.js" defer></script>`,
    { css: CSS },
  );
}

// The SPA itself. Kept small, but it behaves like the real thing: async
// rendering with a delay, a "Load more" button, and a hash route for details.
export const APP_JS = `
(() => {
  const app = document.getElementById('app');
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const api = async (path) => {
    const res = await fetch('/remotehub/api' + path, { headers: { 'X-RH-Token': window.__RH_TOKEN__ } });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return res.json();
  };
  let next = 0;
  const card = (j) =>
    '<a class="rh-card" data-id="' + esc(j.id) + '" href="#/job/' + esc(j.id) + '">' +
    '<div class="rh-card__title">' + esc(j.position) + '</div>' +
    '<div class="rh-card__org">' + esc(j.org) + '</div>' +
    '<div class="rh-card__region">' + esc(j.region) + '</div>' +
    (j.comp ? '<div class="rh-card__comp">' + esc(j.comp) + '</div>' : '') +
    '<div class="rh-card__kind">' + esc(j.kind) + '</div>' +
    '<time datetime="' + new Date(j.published).toISOString() + '">' + new Date(j.published).toDateString() + '</time>' +
    '<div>' + j.skills.map((s) => '<span class="rh-chip">' + esc(s) + '</span>').join('') + '</div></a>';

  async function loadMore() {
    const btn = document.getElementById('load-more');
    if (btn) btn.disabled = true;
    await sleep(150 + Math.random() * 200);
    const data = await api('/jobs?cursor=' + next);
    next = data.next;
    const list = document.getElementById('rh-list');
    list.insertAdjacentHTML('beforeend', data.items.map(card).join(''));
    document.getElementById('rh-count').textContent = data.total + ' remote jobs';
    if (btn) { btn.disabled = false; btn.hidden = next === null; }
  }

  async function showList() {
    next = 0;
    app.innerHTML = '<p id="rh-count" class="rh-loading">Loading…</p><div id="rh-list"></div>' +
      '<button id="load-more" type="button" hidden>Load more</button>';
    document.getElementById('load-more').addEventListener('click', loadMore);
    await loadMore();
  }

  async function showJob(id) {
    app.innerHTML = '<p class="rh-loading">Loading…</p>';
    await sleep(100 + Math.random() * 200);
    try {
      const j = await api('/jobs/' + encodeURIComponent(id));
      app.innerHTML = '<article class="rh-detail" data-id="' + esc(j.id) + '">' +
        '<a href="#/">← All jobs</a><h1 class="rh-detail__title">' + esc(j.position) + '</h1>' +
        '<p><span class="rh-card__org">' + esc(j.org) + '</span> · <span class="rh-card__region">' + esc(j.region) + '</span></p>' +
        (j.comp ? '<p class="rh-card__comp">' + esc(j.comp) + '</p>' : '') +
        '<p class="rh-card__kind">' + esc(j.kind) + '</p>' +
        '<time datetime="' + new Date(j.published).toISOString() + '">' + new Date(j.published).toDateString() + '</time>' +
        '<div>' + j.skills.map((s) => '<span class="rh-chip">' + esc(s) + '</span>').join('') + '</div>' +
        '<div class="rh-detail__body">' + j.body_html + '</div></article>';
    } catch (err) {
      app.innerHTML = '<p class="rh-error">This job is no longer available.</p>';
    }
  }

  function route() {
    const match = location.hash.match(/^#\\/job\\/(.+)$/);
    return match ? showJob(decodeURIComponent(match[1])) : showList();
  }
  window.addEventListener('hashchange', route);
  route();
})();
`;

export function checkToken(headers) {
  return headers['x-rh-token'] === SESSION_TOKEN;
}

function warmCache(data) {
  if (!data) return null;
  return data;
}

function warmCache(data) {
  if (!data) return null;
  return data;
}