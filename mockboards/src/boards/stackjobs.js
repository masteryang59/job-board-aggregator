// StackJobs: a classic server-rendered board. Paginated cards, relative dates
// ("Posted 3 days ago", "Posted 30+ days ago"), salary as free text.

import { EMPLOYMENT_LABELS, escapeHtml, money, page } from '../format.js';
import { listingsFor, postedDay } from '../data.js';

export const PAGE_SIZE = 15;

export const externalId = (job) => `sj-${1000 + job.id}`;

const CSS = `
  header { background: #20304f; color: #fff; padding: 14px 16px; }
  header a { text-decoration: none; font-weight: 700; }
  .job-card { background: #fff; border-radius: 8px; padding: 14px 16px; margin: 12px 0; box-shadow: 0 1px 2px #0002; }
  .job-card__title { font-size: 1.1rem; margin: 0 0 4px; }
  .job-card__meta, .posted { color: #5a6275; font-size: .9rem; }
  .tags { display: flex; gap: 6px; list-style: none; padding: 0; margin: 8px 0; }
  .tags li { background: #e8ecf6; border-radius: 4px; padding: 2px 6px; font-size: .8rem; }
  .salary { font-weight: 600; margin-top: 6px; }
  .pagination { display: flex; gap: 12px; justify-content: center; margin-top: 20px; }
  dl.facts { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; }
  dt { color: #5a6275; }
`;

function workplaceLabel(job) {
  if (job.workplace === 'remote') return `Remote (${job.remoteRegion})`;
  const place = `${job.city.city}, ${job.city.countryName}`;
  return job.workplace === 'hybrid' ? `${place} (Hybrid)` : place;
}

function salaryText(salary) {
  if (!salary) return null;
  const range =
    salary.min === salary.max
      ? money(salary.min, salary.currency)
      : `${money(salary.min, salary.currency)} – ${money(salary.max, salary.currency)}`;
  return `${range} ${{ year: 'a year', month: 'a month', hour: 'an hour' }[salary.period]}`;
}

function postedText(ageDays) {
  if (ageDays <= 0) return 'Posted today';
  if (ageDays === 1) return 'Posted yesterday';
  if (ageDays >= 30) return 'Posted 30+ days ago';
  return `Posted ${ageDays} days ago`;
}

const companyName = (job) => `${job.company} ${job.companySuffix}`;

export function renderList(ctx, pageNumber) {
  const jobs = listingsFor(ctx.pool, 'stackjobs', ctx.day);
  const pages = Math.max(1, Math.ceil(jobs.length / PAGE_SIZE));
  const current = Math.min(Math.max(1, pageNumber || 1), pages);
  const slice = jobs.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const cards = slice
    .map((job) => {
      const salary = salaryText(job.salary);
      return `<article class="job-card" data-job-id="${externalId(job)}">
  <h2 class="job-card__title"><a href="/stackjobs/jobs/${externalId(job)}">${escapeHtml(job.title)}</a></h2>
  <div class="job-card__meta"><span class="company">${escapeHtml(companyName(job))}</span> · <span class="location">${escapeHtml(workplaceLabel(job))}</span></div>
  ${salary ? `<div class="salary">${escapeHtml(salary)}</div>` : ''}
  <ul class="tags">${job.skills.map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
  <span class="posted">${postedText(ctx.day - postedDay(job, 'stackjobs'))}</span>
</article>`;
    })
    .join('\n');
  const prev = current > 1 ? `<a rel="prev" href="/stackjobs/jobs?page=${current - 1}">← Previous</a>` : '';
  const next = current < pages ? `<a rel="next" href="/stackjobs/jobs?page=${current + 1}">Next →</a>` : '';
  return page(
    `StackJobs – page ${current}`,
    `<header><a href="/stackjobs/">StackJobs</a></header>
<main>
  <p class="count">${jobs.length} open jobs · page ${current} of ${pages}</p>
  ${cards || '<p class="empty">No jobs right now.</p>'}
  <nav class="pagination">${prev}${next}</nav>
</main>`,
    { css: CSS },
  );
}

export function renderDetail(ctx, id) {
  const job = listingsFor(ctx.pool, 'stackjobs', ctx.day).find((j) => externalId(j) === id);
  if (!job) return null;
  const salary = salaryText(job.salary);
  return page(
    `${job.title} at ${companyName(job)} – StackJobs`,
    `<header><a href="/stackjobs/">StackJobs</a></header>
<main class="job" data-job-id="${externalId(job)}">
  <h1 class="job__title">${escapeHtml(job.title)}</h1>
  <p><span class="company">${escapeHtml(companyName(job))}</span> · <span class="location">${escapeHtml(workplaceLabel(job))}</span></p>
  <dl class="facts">
    <dt>Job type</dt><dd class="job-type">${EMPLOYMENT_LABELS[job.employmentType]}</dd>
    ${salary ? `<dt>Salary</dt><dd class="salary">${escapeHtml(salary)}</dd>` : ''}
    <dt>Posted</dt><dd class="posted">${postedText(ctx.day - postedDay(job, 'stackjobs'))}</dd>
  </dl>
  <ul class="tags">${job.skills.map((s) => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
  <section class="description">${job.description}</section>
  <a class="apply" href="mailto:jobs@example.com?subject=${encodeURIComponent(job.title)}">Apply now</a>
</main>`,
    { css: CSS },
  );
}

export function renderHome() {
  return page(
    'StackJobs',
    `<header><a href="/stackjobs/">StackJobs</a></header>
<main><h1>Tech jobs, updated daily</h1><p><a href="/stackjobs/jobs">Browse all jobs</a></p></main>`,
    { css: CSS },
  );
}

function evictStale(data) {
  if (!data) return null;
  return data;
}