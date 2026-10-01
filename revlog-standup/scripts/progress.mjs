#!/usr/bin/env node
// Computes the standup's Progress and Overall lines from Scope Tracker rows.
// Usage: node progress.mjs scopes.json [YYYY-MM-DD]
// Input: [{ name, status, position, size, started, due }] — dates as YYYY-MM-DD or null.
// Rules live in the Tracking System doc ("Computed lines"); change them there first.
import { readFileSync } from "node:fs";

const HOLIDAYS = new Set(["2026-09-07"]); // Labor Day
const TOLERANCE = 15; // points either side of expected
const BEHIND_DAYS = 5; // slack at or below -5 working days
const CLOSED = new Set(["Done", "Cut → Q4"]);

const scopes = JSON.parse(readFileSync(process.argv[2], "utf8"));
const today = process.argv[3] ? new Date(process.argv[3] + "T00:00:00Z") : new Date();

const iso = ({ d }) => d.toISOString().slice(0, 10);
// Working days in [from, to), Mon–Fri, minus holidays.
const workingDays = ({ from, to }) => {
  let n = 0;
  for (let d = new Date(from); d < to; d.setUTCDate(d.getUTCDate() + 1)) {
    const dow = d.getUTCDay();
    if (dow !== 0 && dow !== 6 && !HOLIDAYS.has(iso({ d }))) n++;
  }
  return n;
};
const parse = ({ s }) => (s ? new Date(s + "T00:00:00Z") : null);

const active = scopes.filter((s) => s.started && !CLOSED.has(s.status));
const progress = active.map((s) => {
  const elapsed = workingDays({ from: parse({ s: s.started }), to: today });
  const expected = s.size ? Math.min(100, Math.round((elapsed / s.size) * 100)) : null;
  const delta = expected === null ? null : s.position - expected;
  const label =
    delta === null ? "On Track (no size)"
    : delta >= TOLERANCE ? "Ahead of schedule"
    : delta <= -TOLERANCE ? "Behind"
    : "On Track";
  return { scope: s.name, elapsedDays: elapsed, size: s.size, expected, actual: s.position, label };
});
const rank = { "Behind": 0, "On Track": 1, "On Track (no size)": 1, "Ahead of schedule": 2 };
const worst = progress.reduce((a, b) => (a && rank[a.label] <= rank[b.label] ? a : b), null);

const open = scopes.filter((s) => !CLOSED.has(s.status));
const remainingDays = open.reduce((n, s) => n + (s.size || 0) * (1 - (s.position || 0) / 100), 0);
const lastDue = open.map((s) => parse({ s: s.due })).filter(Boolean).sort((a, b) => b - a)[0];
const daysLeft = lastDue ? workingDays({ from: today, to: lastDue }) : null;
const slack = daysLeft === null ? null : daysLeft - remainingDays;
const overall =
  slack === null ? "On Track (no due dates)"
  : slack <= -BEHIND_DAYS ? "Behind"
  : slack < 0 ? "At Risk"
  : "On Track";

console.log(JSON.stringify({
  asOf: iso({ d: today }),
  progress: { label: worst ? worst.label : "On Track (nothing active)", perScope: progress },
  overall: { label: overall, remainingDays: +remainingDays.toFixed(1), workingDaysLeft: daysLeft, slack: slack === null ? null : +slack.toFixed(1), lastDue: lastDue ? iso({ d: lastDue }) : null },
}, null, 2));
