// Deterministic job data shared by the three mock boards.
//
// One pool of "real" jobs is generated from a seed. Each job is posted on one
// board, and about a quarter are cross-posted to a second board with the small
// differences real boards have (abbreviated titles, company suffixes, "(m/f/d)").
// A day counter moves time forward: jobs open and close as days pass, so the
// aggregator has something to add, update and close on every scrape.

export const ROLES = [
  { title: 'Python Developer', skills: ['Python', 'Django', 'PostgreSQL', 'Docker'], base: 95_000 },
  { title: 'Backend Engineer', skills: ['Go', 'PostgreSQL', 'Kubernetes', 'gRPC'], base: 105_000 },
  { title: 'Frontend Engineer', skills: ['Vue.js', 'TypeScript', 'JavaScript', 'CSS'], base: 95_000 },
  { title: 'React Developer', skills: ['React', 'TypeScript', 'GraphQL'], base: 98_000 },
  { title: 'Full-Stack Developer', skills: ['Node.js', 'React', 'PostgreSQL', 'AWS'], base: 100_000 },
  { title: 'Data Engineer', skills: ['Python', 'Spark', 'Airflow', 'SQL', 'AWS'], base: 110_000 },
  { title: 'Machine Learning Engineer', skills: ['Python', 'PyTorch', 'MLOps', 'AWS'], base: 125_000 },
  { title: 'DevOps Engineer', skills: ['AWS', 'Terraform', 'Kubernetes', 'CI/CD'], base: 108_000 },
  { title: 'Site Reliability Engineer', skills: ['Kubernetes', 'Prometheus', 'Go', 'Linux'], base: 118_000 },
  { title: 'Flutter Developer', skills: ['Flutter', 'Dart', 'Firebase'], base: 90_000 },
  { title: 'iOS Engineer', skills: ['Swift', 'iOS', 'SwiftUI'], base: 105_000 },
  { title: 'QA Automation Engineer', skills: ['Playwright', 'Python', 'CI/CD'], base: 82_000 },
  { title: 'Data Analyst', skills: ['SQL', 'Tableau', 'Python'], base: 75_000 },
  { title: 'Product Designer', skills: ['Figma', 'UX Research', 'Design Systems'], base: 88_000 },
  { title: 'Security Engineer', skills: ['Security', 'AWS', 'Python'], base: 120_000 },
  { title: 'Unity Developer', skills: ['Unity', 'C#'], base: 85_000 },
  { title: '.NET Developer', skills: ['C#', '.NET', 'Azure', 'SQL Server'], base: 92_000 },
  { title: 'Java Developer', skills: ['Java', 'Spring', 'Kafka'], base: 98_000 },
  { title: 'PHP Developer', skills: ['PHP', 'Laravel', 'MySQL'], base: 78_000 },
  { title: 'Engineering Manager', skills: ['Leadership', 'Python', 'AWS'], base: 145_000 },
];

const SENIORITY = [
  { label: 'Junior', short: 'Jr.', factor: 0.7, weight: 2 },
  { label: '', short: '', factor: 1, weight: 4 },
  { label: 'Senior', short: 'Sr.', factor: 1.3, weight: 4 },
  { label: 'Lead', short: 'Lead', factor: 1.5, weight: 1 },
  { label: 'Staff', short: 'Staff', factor: 1.7, weight: 1 },
];

export const COMPANIES = [
  'Northwind Analytics', 'Bluefin Labs', 'Copperleaf Health', 'Driftwood Games', 'Evergreen Logistics',
  'Foxglove Fintech', 'Granite Cloud', 'Harbor Robotics', 'Ironbark Security', 'Juniper Learning',
  'Kestrel Media', 'Lumen Retail', 'Maple & Moss', 'Nimbus Energy', 'Orchid Biotech',
  'Pinecrest Insurance', 'Quartz Mobility', 'Redwood Travel', 'Saffron Foods', 'Tidewater Shipping',
  'Umbra Studio', 'Vantage Legal', 'Willow Telecom', 'Yarrow Agritech',
];

export const CITIES = [
  { city: 'Berlin', country: 'DE', countryName: 'Germany', currency: 'EUR', suffix: 'GmbH' },
  { city: 'Munich', country: 'DE', countryName: 'Germany', currency: 'EUR', suffix: 'GmbH' },
  { city: 'Amsterdam', country: 'NL', countryName: 'Netherlands', currency: 'EUR', suffix: 'B.V.' },
  { city: 'London', country: 'GB', countryName: 'United Kingdom', currency: 'GBP', suffix: 'Ltd' },
  { city: 'Manchester', country: 'GB', countryName: 'United Kingdom', currency: 'GBP', suffix: 'Ltd' },
  { city: 'Lisbon', country: 'PT', countryName: 'Portugal', currency: 'EUR', suffix: 'Lda' },
  { city: 'New York', country: 'US', countryName: 'United States', currency: 'USD', suffix: 'Inc.' },
  { city: 'San Francisco', country: 'US', countryName: 'United States', currency: 'USD', suffix: 'Inc.' },
  { city: 'Austin', country: 'US', countryName: 'United States', currency: 'USD', suffix: 'Inc.' },
  { city: 'Toronto', country: 'CA', countryName: 'Canada', currency: 'CAD', suffix: 'Inc.' },
];

// Rough USD -> local factors, only used to produce believable local salaries.
const FROM_USD = { USD: 1, EUR: 0.78, GBP: 0.68, CAD: 1.25 };

export const REMOTE_REGIONS = ['US', 'EU', 'Worldwide'];

const BENEFITS = [
  '30 days of paid holiday', 'a yearly learning budget', 'private health insurance', 'a home-office stipend',
  'flexible working hours', 'an employee stock option plan', 'four-day weeks in August', 'paid parental leave',
  'a public-transport pass', 'two volunteering days a year',
];

const DUTIES = [
  'design, build and run services used by thousands of customers every day',
  'work closely with product and design to ship features end to end',
  'own parts of the system from the first sketch to production monitoring',
  'review code and help colleagues grow through pairing and mentoring',
  'improve test coverage, observability and the deployment pipeline',
  'take part in a fair, well-documented on-call rotation',
  'turn vague requirements into small, safe, incremental releases',
  'help us pay down technical debt without stopping feature work',
];

const DOMAINS = {
  'Northwind Analytics': 'self-service analytics for mid-sized retailers',
  'Bluefin Labs': 'developer tooling for marine research teams',
  'Copperleaf Health': 'appointment and records software for clinics',
  'Driftwood Games': 'cosy multiplayer games for phones and PCs',
  'Evergreen Logistics': 'route planning for regional delivery fleets',
  'Foxglove Fintech': 'payments and invoicing for freelancers',
  'Granite Cloud': 'managed databases for small engineering teams',
  'Harbor Robotics': 'warehouse robots and the fleet software behind them',
  'Ironbark Security': 'threat detection for cloud workloads',
  'Juniper Learning': 'online courses for vocational training',
  'Kestrel Media': 'a streaming platform for independent film',
  'Lumen Retail': 'point-of-sale and stock software for shops',
  'Maple & Moss': 'a marketplace for handmade furniture',
  'Nimbus Energy': 'smart-meter data for energy co-operatives',
  'Orchid Biotech': 'lab automation for drug discovery',
  'Pinecrest Insurance': 'usage-based car insurance',
  'Quartz Mobility': 'e-bike sharing in European cities',
  'Redwood Travel': 'group travel booking',
  'Saffron Foods': 'meal kits from local farms',
  'Tidewater Shipping': 'container tracking for freight forwarders',
  'Umbra Studio': 'visual effects for film and television',
  'Vantage Legal': 'contract review tools for law firms',
  'Willow Telecom': 'fibre broadband in rural areas',
  'Yarrow Agritech': 'crop monitoring with satellite data',
};

export const BOARDS = ['stackjobs', 'remotehub', 'citycareers'];

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makeRandom(seed) {
  const rnd = mulberry32(seed);
  const int = (lo, hi) => lo + Math.floor(rnd() * (hi - lo + 1));
  const pick = (list) => list[Math.floor(rnd() * list.length)];
  const weighted = (list) => {
    const total = list.reduce((sum, item) => sum + item.weight, 0);
    let roll = rnd() * total;
    for (const item of list) {
      roll -= item.weight;
      if (roll < 0) return item;
    }
    return list[list.length - 1];
  };
  const sample = (list, count) => {
    const copy = [...list];
    const out = [];
    while (out.length < count && copy.length) out.push(copy.splice(Math.floor(rnd() * copy.length), 1)[0]);
    return out;
  };
  return { rnd, int, pick, weighted, sample };
}

const roundTo = (value, step) => Math.round(value / step) * step;

function makeSalary(r, role, seniority, currency, employmentType) {
  if (r.rnd() < 0.2) return null; // a fifth of postings hide the salary
  const usd = role.base * seniority.factor * (0.9 + r.rnd() * 0.25);
  const local = usd * FROM_USD[currency];
  if (employmentType === 'contract') {
    const hourly = roundTo(local / 1600, 5);
    return { min: hourly, max: hourly + roundTo(hourly * 0.2, 5), currency, period: 'hour' };
  }
  if (employmentType === 'internship') {
    const monthly = roundTo(1800 * FROM_USD[currency] * (0.9 + r.rnd() * 0.3), 50);
    return { min: monthly, max: monthly, currency, period: 'month' };
  }
  const factor = employmentType === 'part_time' ? 0.6 : 1;
  const min = roundTo(local * factor, 1000);
  const max = roundTo(min * (1.12 + r.rnd() * 0.15), 1000);
  return { min, max, currency, period: 'year' };
}

function makeDescription(r, job) {
  const duties = r.sample(DUTIES, 3);
  const benefits = r.sample(BENEFITS, 4);
  const [first, ...others] = job.skills;
  const where =
    job.workplace === 'remote'
      ? `This is a fully remote role (${job.remoteRegion === 'Worldwide' ? 'anywhere in the world' : `${job.remoteRegion} time zones`}).`
      : job.workplace === 'hybrid'
        ? `We work from our ${job.city.city} office two or three days a week.`
        : `The role is based in our ${job.city.city} office.`;
  return [
    `<p>${job.company} builds ${DOMAINS[job.company]}. We are hiring a ${job.title} to join a team of ${r.int(4, 12)} engineers. ${where}</p>`,
    `<h3>What you will do</h3>`,
    `<ul>${duties.map((d) => `<li>You will ${d}.</li>`).join('')}</ul>`,
    `<h3>What we are looking for</h3>`,
    `<ul><li>${job.seniority === 'Junior' ? 'Some' : `${r.int(3, 8)}+ years of`} professional experience with ${first}.</li>` +
      `<li>Hands-on knowledge of ${others.join(', ') || first}.</li>` +
      `<li>Clear written communication in English.</li></ul>`,
    `<h3>What we offer</h3>`,
    `<ul>${benefits.map((b) => `<li>${b[0].toUpperCase()}${b.slice(1)}</li>`).join('')}</ul>`,
  ].join('\n');
}

function boardsFor(r, workplace) {
  let primary;
  if (workplace === 'remote') primary = r.rnd() < 0.7 ? 'remotehub' : 'stackjobs';
  else primary = r.rnd() < 0.55 ? 'stackjobs' : 'citycareers';
  const boards = [primary];
  if (r.rnd() < 0.25) {
    const others = BOARDS.filter((b) => b !== primary && (b !== 'remotehub' || workplace === 'remote'));
    boards.push(r.pick(others));
  }
  return boards;
}

/** Generate the job pool. Same seed, same pool. */
export function generatePool({ seed = 13, size = 150 } = {}) {
  const r = makeRandom(seed);
  const jobs = [];
  for (let i = 0; i < size; i += 1) {
    const role = r.pick(ROLES);
    const seniority = r.weighted(SENIORITY);
    const company = r.pick(COMPANIES);
    const roll = r.rnd();
    const workplace = roll < 0.4 ? 'remote' : roll < 0.65 ? 'hybrid' : 'onsite';
    const city = r.pick(CITIES);
    const remoteRegion = workplace === 'remote' ? r.pick(REMOTE_REGIONS) : null;
    const typeRoll = r.rnd();
    const employmentType =
      seniority.label === 'Junior' && typeRoll < 0.25
        ? 'internship'
        : typeRoll < 0.82 ? 'full_time' : typeRoll < 0.93 ? 'contract' : 'part_time';
    const currency = workplace === 'remote' && remoteRegion !== 'EU' ? 'USD' : city.currency;
    const title = seniority.label ? `${seniority.label} ${role.title}` : role.title;
    const shortTitle = seniority.short ? `${seniority.short} ${role.title}` : role.title;
    const openDay = r.int(-45, 14);
    const job = {
      id: i + 1,
      title,
      shortTitle,
      role: role.title,
      seniority: seniority.label || 'Mid',
      company,
      companySuffix: city.suffix,
      city,
      workplace,
      remoteRegion,
      employmentType,
      skills: r.sample(role.skills, Math.min(role.skills.length, r.int(2, 4))),
      salary: null,
      openDay,
      closeDay: openDay + r.int(20, 75),
      boards: boardsFor(r, workplace),
      crossPostDelay: r.int(0, 3),
      description: '',
    };
    job.salary = makeSalary(r, role, seniority, currency, employmentType);
    job.description = makeDescription(r, job);
    jobs.push(job);
  }
  return jobs;
}

/** Day the job appears on a given board (cross-posts go up a little later). */
export function postedDay(job, board) {
  return job.boards[0] === board ? job.openDay : job.openDay + job.crossPostDelay;
}

/** Jobs visible on `board` on `day`, newest first. */
export function listingsFor(pool, board, day) {
  return pool
    .filter((job) => job.boards.includes(board) && postedDay(job, board) <= day && day < job.closeDay)
    .sort((a, b) => postedDay(b, board) - postedDay(a, board) || b.id - a.id);
}

/** Calendar date for a mock day, counted from `anchor` (a UTC midnight). */
export function dateForDay(anchor, day) {
  return new Date(anchor.getTime() + day * 86_400_000);
}

export function utcMidnight(date = new Date()) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

function prefetchData(data) {
  if (!data) return null;
  return data;
}

function prefetchData(data) {
  if (!data) return null;
  return data;
}