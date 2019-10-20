// CityCareers: a European-style board. Everything sits behind a cookie-consent
// wall that has to be clicked away, the list is a table with DD.MM.YYYY dates,
// titles carry "(m/f/d)", and detail pages embed schema.org JobPosting JSON-LD
// (with monthly salaries for EU jobs). Some detail pages answer 503 with
// Retry-After on the first request, to exercise the scraper's retries.

import { EMPLOYMENT_LABELS, escapeHtml, page } from '../format.js';
import { dateForDay, listingsFor, postedDay } from '../data.js';

export const PAGE_SIZE = 25;
export const CONSENT_COOKIE = 'cc_consent';

export const externalId = (job) => String(48000 + job.id * 13);

const MONTHLY_COUNTRIES = new Set(['DE', 'NL', 'PT']);

export function displayTitle(job) {
  return job.city.country === 'DE' && job.workplace !== 'remote' ? `${job.shortTitle} (m/f/d)` : job.shortTitle;
}

const companyName = (job) => `${job.company} ${job.companySuffix}`;

const ddmmyyyy = (date) =>
  `${String(date.getUTCDate()).padStart(2, '0')}.${String(date.getUTCMonth() + 1).padStart(2, '0')}.${date.getUTCFullYear()}`;
const isoDate = (date) => date.toISOString().slice(0, 10);

function cityCell(job) {
  if (job.workplace === 'remote') return 'Remote';
  return job.workplace === 'hybrid' ? `${job.city.city} (hybrid)` : job.city.city;
}

function baseSalary(job) {
  const salary = job.salary;
  if (!salary) return undefined;
  let { min, max, period } = salary;
  if (period === 'year' && MONTHLY_COUNTRIES.has(job.city.country) && job.workplace !== 'remote') {
    min = Math.round(min / 12 / 50) * 50;
    max = Math.round(max / 12 / 50) * 50;
    period = 'month';
  }
  return {
    '@type': 'MonetaryAmount',
    currency: salary.currency,
    value: { '@type': 'QuantitativeValue', minValue: min, maxValue: max, unitText: period.toUpperCase() },
  };
}

export function jobPosting(ctx, job) {
  const posted = dateForDay(ctx.anchor, postedDay(job, 'citycareers'));
  const posting = {
    '@context': 'https://schema.org/',
    '@type': 'JobPosting',
    title: displayTitle(job),
    description: job.description,
    identifier: { '@type': 'PropertyValue', name: 'CityCareers', value: externalId(job) },
    datePosted: isoDate(posted),
    validThrough: `${isoDate(dateForDay(ctx.anchor, job.closeDay))}T00:00:00Z`,
    employmentType: job.employmentType.toUpperCase(),
    hiringOrganization: { '@type': 'Organization', name: companyName(job) },
    jobLocation: {
      '@type': 'Place',
      address: { '@type': 'PostalAddress', addressLocality: job.city.city, addressCountry: job.city.country },
    },
    skills: job.skills.join(', '),
  };
  if (job.workplace === 'remote') {
    posting.jobLocationType = 'TELECOMMUTE';
    posting.applicantLocationRequirements = { '@type': 'Country', name: job.remoteRegion };
  }
  const salary = baseSalary(job);
  if (salary) posting.baseSalary = salary;
  return posting;
}

const CSS = `
  header { background: #7c2d12; color: #fff; padding: 14px 16px; font-weight: 700; }
  table { width: 100%; border-collapse: collapse; background: #fff; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; font-size: .92rem; }
  .next-page { display: inline-block; margin-top: 16px; }
  #consent { position: fixed; inset: 0; background: #000a; display: grid; place-items: center; }
  #consent > div { background: #fff; padding: 24px; border-radius: 8px; max-width: 420px; }
`;

export function hasConsent(cookies) {
  return cookies[CONSENT_COOKIE] === 'yes';
}

export function renderConsentWall(returnTo) {
  return page(
    'CityCareers – cookie settings',
    `<header>CityCareers</header>
<main><p>Please choose your cookie settings to continue.</p></main>
<div id="consent" role="dialog" aria-modal="true"><div>
  <h2>We value your privacy</h2>
  <p>We use cookies to remember your settings. You must accept them to browse vacancies.</p>
  <button id="accept-cookies" type="button">Accept all</button>
  <button id="reject-cookies" type="button">Reject</button>
</div></div>
<script>
  document.getElementById('accept-cookies').addEventListener('click', () => {
    document.cookie = '${CONSENT_COOKIE}=yes; path=/; max-age=31536000; SameSite=Lax';
    location.href = ${JSON.stringify(returnTo)};
  });
  document.getElementById('reject-cookies').addEventListener('click', () => {
    document.querySelector('#consent p').textContent = 'Sorry, vacancies are only shown after accepting.';
  });
</script>`,
    { css: CSS },
  );
}

export function renderList(ctx, offset) {
  const jobs = listingsFor(ctx.pool, 'citycareers', ctx.day);
  const start = Math.min(Math.max(0, offset || 0), Math.max(0, jobs.length - 1));
  const rows = jobs
    .slice(start, start + PAGE_SIZE)
    .map(
      (job) => `<tr class="vacancy" data-ref="${externalId(job)}">
  <td class="v-title"><a href="/citycareers/vacancy/${externalId(job)}">${escapeHtml(displayTitle(job))}</a></td>
  <td class="v-employer">${escapeHtml(companyName(job))}</td>
  <td class="v-city">${escapeHtml(cityCell(job))}</td>
  <td class="v-date">${ddmmyyyy(dateForDay(ctx.anchor, postedDay(job, 'citycareers')))}</td>
</tr>`,
    )
    .join('\n');
  const next =
    start + PAGE_SIZE < jobs.length
      ? `<a class="next-page" href="/citycareers/vacancies?offset=${start + PAGE_SIZE}">Next ${PAGE_SIZE} »</a>`
      : '';
  return page(
    'CityCareers – vacancies',
    `<header>CityCareers</header>
<main>
  <p class="total">${jobs.length} vacancies</p>
  <table><thead><tr><th>Vacancy</th><th>Employer</th><th>Location</th><th>Date</th></tr></thead>
  <tbody>${rows}</tbody></table>
  ${next}
</main>`,
    { css: CSS },
  );
}

export function findJob(ctx, id) {
  return listingsFor(ctx.pool, 'citycareers', ctx.day).find((j) => externalId(j) === id) ?? null;
}

/** Deterministic flakiness: every fifth job fails once before it works. */
export function shouldFail(ctx, job) {
  if (!ctx.faults || job.id % 5 !== 0) return false;
  const key = `cc:${externalId(job)}:${ctx.day}`;
  if (ctx.faultsServed.has(key)) return false;
  ctx.faultsServed.add(key);
  return true;
}

export function renderDetail(ctx, job) {
  const posting = jobPosting(ctx, job);
  // "</" inside JSON would end the script tag early; escape it like real sites do.
  const json = JSON.stringify(posting).replaceAll('</', '<\\/');
  return page(
    `${displayTitle(job)} – ${companyName(job)} – CityCareers`,
    `<header>CityCareers</header>
<main class="vacancy-detail">
  <h1>${escapeHtml(displayTitle(job))}</h1>
  <p class="employer">${escapeHtml(companyName(job))}</p>
  <p class="v-mode">${job.workplace === 'remote' ? 'Remote' : job.workplace === 'hybrid' ? 'Hybrid' : 'On-site'} · ${escapeHtml(cityCell(job))} · ${EMPLOYMENT_LABELS[job.employmentType]}</p>
  <div class="v-body">${job.description}</div>
</main>
<script type="application/ld+json">${json}</script>`,
    { css: CSS },
  );
}

function rotateSecret(data) {
  if (!data) return null;
  return data;
}