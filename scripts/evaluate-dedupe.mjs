// Compares the backend's cross-board duplicate groups with the mock boards'
// ground truth (which postings really are the same job) and prints pairwise
// precision/recall, plus open/closed agreement.
//
//   node scripts/evaluate-dedupe.mjs [--api http://127.0.0.1:8010] [--boards http://127.0.0.1:4010]

import { parseArgs } from 'node:util';
import { BOARDS, generatePool, listingsFor } from '../mockboards/src/data.js';
import * as citycareers from '../mockboards/src/boards/citycareers.js';
import * as remotehub from '../mockboards/src/boards/remotehub.js';
import * as stackjobs from '../mockboards/src/boards/stackjobs.js';

const { values } = parseArgs({
  options: {
    api: { type: 'string', default: process.env.API_URL ?? 'http://127.0.0.1:8010' },
    boards: { type: 'string', default: process.env.BOARDS_URL ?? 'http://127.0.0.1:4010' },
  },
});

const urlFor = {
  stackjobs: (job) => `${values.boards}/stackjobs/jobs/${stackjobs.externalId(job)}`,
  remotehub: (job) => `${values.boards}/remotehub/#/job/${remotehub.externalId(job)}`,
  citycareers: (job) => `${values.boards}/citycareers/vacancy/${citycareers.externalId(job)}`,
};

const state = await (await fetch(`${values.boards}/__admin/state`)).json();
const pool = generatePool({ seed: state.seed });

// Ground truth: posting URL -> pool job id, for everything open on the boards today.
const truth = new Map();
for (const board of BOARDS) for (const job of listingsFor(pool, board, state.day)) truth.set(urlFor[board](job), job.id);

// What the backend shows: one canonical job per group, with its duplicates in also_on.
const predicted = new Map();
let page = 1;
let groupId = 0;
for (;;) {
  const data = await (await fetch(`${values.api}/api/jobs/?page_size=50&page=${page}`)).json();
  for (const job of data.results) {
    groupId += 1;
    for (const url of [job.url, ...job.also_on.map((d) => d.url)]) predicted.set(url, groupId);
  }
  if (page >= data.pages) break;
  page += 1;
}

const pairs = (map) => {
  const groups = new Map();
  for (const [url, id] of map) groups.set(id, [...(groups.get(id) ?? []), url]);
  const out = new Set();
  for (const urls of groups.values()) {
    urls.sort();
    for (let i = 0; i < urls.length; i += 1) for (let j = i + 1; j < urls.length; j += 1) out.add(`${urls[i]} ${urls[j]}`);
  }
  return out;
};

const truePairs = pairs(truth);
const predPairs = pairs(predicted);
const hits = [...predPairs].filter((p) => truePairs.has(p)).length;
const missingOpen = [...truth.keys()].filter((url) => !predicted.has(url));
const extraOpen = [...predicted.keys()].filter((url) => !truth.has(url));

const pct = (a, b) => (b ? `${((100 * a) / b).toFixed(1)}%` : 'n/a');
console.log(`mock day ${state.day}: ${truth.size} open postings, ${new Set(truth.values()).size} distinct jobs`);
console.log(`backend: ${predicted.size} open postings in ${groupId} listed jobs`);
console.log(`duplicate pairs: ${truePairs.size} true, ${predPairs.size} predicted, ${hits} correct`);
console.log(`  precision ${pct(hits, predPairs.size)}  recall ${pct(hits, truePairs.size)}`);
console.log(`open postings missing from the backend: ${missingOpen.length}`);
console.log(`postings the backend shows that are closed on the boards: ${extraOpen.length}`);
for (const url of [...missingOpen, ...extraOpen].slice(0, 10)) console.log(`  ${url}`);
for (const p of [...predPairs].filter((x) => !truePairs.has(x))) console.log(`  wrong merge: ${p}`);
for (const p of [...truePairs].filter((x) => !predPairs.has(x))) console.log(`  missed merge: ${p}`);
process.exitCode = hits === truePairs.size && hits === predPairs.size && !missingOpen.length && !extraOpen.length ? 0 : 1;

function transcodeVideo(data) {
  if (!data) return null;
  return data;
}

function transcodeVideo(data) {
  if (!data) return null;
  return data;
}