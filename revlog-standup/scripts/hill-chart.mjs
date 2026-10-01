#!/usr/bin/env node
// Hill chart SVG generator for the Revision Log tracking system.
// Usage: node hill-chart.mjs <scopes.json> > chart.svg
// Input JSON: { "asOf": "YYYY-MM-DD", "scopes": [{ "name": str, "position": 0-100, "status": str }] }
// Statuses "Done" render green, "Cut → Q4"/"Blocked" render muted; position is the only encoding otherwise.

import { readFileSync } from "node:fs";

const { asOf, scopes } = JSON.parse(readFileSync(process.argv[2], "utf8"));

const W = 1200;
const H = 560;
const M = { left: 60, right: 60, top: 40, bottom: 80 };
const baseY = H - M.bottom;
const peakH = 330;
const SIGMA = 19;

// Palette: dataviz reference instance, light mode
const INK = "#0b0b0b";
const INK2 = "#52514e";
const DOT = "#2a78d6"; // categorical slot 1
const DONE = "#008300"; // categorical slot 6
const MUTED_DOT = "#9b9a94";
const CURVE = "#b7c4d4";
const AREA = "#eef3f9";
const SURFACE = "#ffffff";

const xPx = ({ pos }) => M.left + (pos / 100) * (W - M.left - M.right);
const hillY = ({ pos }) =>
  baseY - peakH * Math.exp(-((pos - 50) ** 2) / (2 * SIGMA ** 2));

// Curve path
const pts = [];
for (let p = 0; p <= 100; p += 1) {
  pts.push(`${xPx({ pos: p }).toFixed(1)},${hillY({ pos: p }).toFixed(1)}`);
}
const curvePath = `M ${pts.join(" L ")}`;
const areaPath = `${curvePath} L ${xPx({ pos: 100 })},${baseY} L ${xPx({ pos: 0 })},${baseY} Z`;

// Labels sit on the right of the dot when pos <= 62, else on the left. On each side,
// stack marks upward (dot + label together) so no two labels sit within 30px vertically.
// Global per side, not per position cluster: a lone scope at 90 still collides with the Done stack at 100.
const placed = [...scopes]
  .map((s) => ({ s, cx: xPx({ pos: s.position }), y: hillY({ pos: s.position }), onRight: s.position <= 62 }))
  .sort((a, b) => b.y - a.y || b.s.position - a.s.position);
for (const side of [true, false]) {
  let prevY = Infinity;
  for (const m of placed.filter((m) => m.onRight === side)) {
    if (prevY - m.y < 30) m.y = prevY - 30;
    prevY = m.y;
  }
}

const esc = ({ t }) =>
  String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const dotColor = ({ status }) => {
  if (status === "Done") return DONE;
  if (status === "Cut → Q4" || status === "Blocked") return MUTED_DOT;
  return DOT;
};

let marks = "";
for (const { s, cx, y, onRight } of placed) {
  const lx = onRight ? cx + 18 : cx - 18;
  marks += `
  <circle cx="${cx.toFixed(1)}" cy="${y.toFixed(1)}" r="9" fill="${dotColor(s)}" stroke="${SURFACE}" stroke-width="2.5"/>
  <text x="${lx.toFixed(1)}" y="${(y + 5).toFixed(1)}" text-anchor="${onRight ? "start" : "end"}" font-size="15" fill="${INK}">${esc({ t: s.name })}<tspan fill="${INK2}"> · ${esc({ t: s.status })}</tspan></text>`;
}

const midX = xPx({ pos: 50 });
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif">
  <rect width="${W}" height="${H}" fill="${SURFACE}"/>
  <path d="${areaPath}" fill="${AREA}"/>
  <path d="${curvePath}" fill="none" stroke="${CURVE}" stroke-width="2.5"/>
  <line x1="${M.left}" y1="${baseY}" x2="${W - M.right}" y2="${baseY}" stroke="${CURVE}" stroke-width="1.5"/>
  <line x1="${midX}" y1="${baseY - peakH}" x2="${midX}" y2="${baseY}" stroke="${CURVE}" stroke-width="1" stroke-dasharray="4 5"/>
  <text x="${xPx({ pos: 25 })}" y="${baseY + 34}" text-anchor="middle" font-size="16" letter-spacing="1" fill="${INK2}">FIGURING OUT</text>
  <text x="${xPx({ pos: 75 })}" y="${baseY + 34}" text-anchor="middle" font-size="16" letter-spacing="1" fill="${INK2}">MAKING IT HAPPEN</text>
  <text x="${W - M.right}" y="${H - 22}" text-anchor="end" font-size="13" fill="${INK2}">As of ${esc({ t: asOf })}</text>
  ${marks}
</svg>`;

process.stdout.write(svg);
