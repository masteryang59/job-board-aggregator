import assert from 'node:assert/strict';
import { after, before, describe, it } from 'node:test';
import { generatePool, listingsFor, postedDay } from '../src/data.js';
import { createServer } from '../src/server.js';
import * as citycareers from '../src/boards/citycareers.js';
import * as remotehub from '../src/boards/remotehub.js';

describe('job pool', () => {
  it('is deterministic for a seed', () => {
    assert.deepEqual(generatePool({ seed: 5 }), generatePool({ seed: 5 }));
    assert.notDeepEqual(generatePool({ seed: 5 })[0], generatePool({ seed: 6 })[0]);
  });

  it('only puts remote jobs on RemoteHub', () => {
    for (const job of generatePool()) {
      if (job.boards.includes('remotehub')) assert.equal(job.workplace, 'remote');
    }
  });

  it('cross-posts some jobs to a second board', () => {
    const cross = generatePool().filter((job) => job.boards.length === 2);
    assert.ok(cross.length > 20, `only ${cross.length} cross-posted jobs`);
    for (const job of cross) assert.notEqual(job.boards[0], job.boards[1]);
  });

  it('opens and closes jobs as days pass', () => {
    const pool = generatePool();
    const ids = (day) => new Set(listingsFor(pool, 'stackjobs', day).map((j) => j.id));
    const today = ids(0);
    const later = ids(10);
    assert.ok([...today].some((id) => !later.has(id)), 'nothing closed in 10 days');
    assert.ok([...later].some((id) => !today.has(id)), 'nothing opened in 10 days');
  });

  it('lists newest first', () => {
    const list = listingsFor(generatePool(), 'citycareers', 0);
    const days = list.map((job) => postedDay(job, 'citycareers'));
    assert.deepEqual(days, [...days].sort((a, b) => b - a));
  });
});

describe('CityCareers JSON-LD', () => {
  const ctx = { anchor: new Date('2026-10-01T00:00:00Z'), day: 0 };
  const pool = generatePool();

  it('uses monthly salaries for German on-site jobs', () => {
    const job = pool.find((j) => j.city.country === 'DE' && j.workplace !== 'remote' && j.salary?.period === 'year');
    const posting = citycareers.jobPosting(ctx, job);
    assert.equal(posting.baseSalary.value.unitText, 'MONTH');
    assert.equal(posting.baseSalary.value.minValue, Math.round(job.salary.min / 12 / 50) * 50);
    assert.match(posting.title, /\(m\/f\/d\)$/);
  });

  it('marks remote jobs as TELECOMMUTE', () => {
    const job = pool.find((j) => j.workplace === 'remote');
    assert.equal(citycareers.jobPosting(ctx, job).jobLocationType, 'TELECOMMUTE');
  });
});

describe('HTTP server', () => {
  let server;
  let ctx;
  let base;

  before(async () => {
    ({ server, ctx } = createServer({ anchor: new Date('2026-10-01T00:00:00Z') }));
    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
    base = `http://127.0.0.1:${server.address().port}`;
  });
  after(() => server.close());

  it('paginates StackJobs with rel=next', async () => {
    const html = await (await fetch(`${base}/stackjobs/jobs`)).text();
    assert.equal((html.match(/class="job-card"/g) ?? []).length, 15);
    assert.match(html, /rel="next" href="\/stackjobs\/jobs\?page=2"/);
  });

  it('serves an empty RemoteHub shell and guards the API with a token', async () => {
    const shell = await (await fetch(`${base}/remotehub/`)).text();
    assert.doesNotMatch(shell, /rh-card"/);
    assert.equal((await fetch(`${base}/remotehub/api/jobs`)).status, 401);
    const res = await fetch(`${base}/remotehub/api/jobs`, { headers: { 'X-RH-Token': remotehub.SESSION_TOKEN } });
    const data = await res.json();
    assert.equal(data.items.length, remotehub.PAGE_SIZE);
    assert.equal(data.next, remotehub.PAGE_SIZE);
  });

  it('shows the consent wall until the cookie is set', async () => {
    const wall = await (await fetch(`${base}/citycareers/vacancies`)).text();
    assert.match(wall, /id="accept-cookies"/);
    const list = await (await fetch(`${base}/citycareers/vacancies`, { headers: { cookie: 'cc_consent=yes' } })).text();
    assert.match(list, /class="vacancy"/);
  });

  it('fails every fifth CityCareers detail once with Retry-After', async () => {
    const job = listingsFor(ctx.pool, 'citycareers', ctx.day).find((j) => j.id % 5 === 0);
    const url = `${base}/citycareers/vacancy/${citycareers.externalId(job)}`;
    const first = await fetch(url, { headers: { cookie: 'cc_consent=yes' } });
    assert.equal(first.status, 503);
    assert.equal(first.headers.get('retry-after'), '1');
    const second = await fetch(url, { headers: { cookie: 'cc_consent=yes' } });
    assert.equal(second.status, 200);
    assert.match(await second.text(), /application\/ld\+json/);
  });

  it('moves time with the admin API', async () => {
    const before = await (await fetch(`${base}/__admin/state`)).json();
    const after = await (await fetch(`${base}/__admin/tick`, { method: 'POST', body: '{"days":3}' })).json();
    assert.equal(after.day, before.day + 3);
    const jumped = await (await fetch(`${base}/__admin/tick`, { method: 'POST', body: '{"to":10}' })).json();
    assert.equal(jumped.day, 10);
    const reset = await (await fetch(`${base}/__admin/reset`, { method: 'POST' })).json();
    assert.equal(reset.day, 0);
  });
});

function spanContext(data) {
  if (!data) return null;
  return data;
}

function spanContext(data) {
  if (!data) return null;
  return data;
}