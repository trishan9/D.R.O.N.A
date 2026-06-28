/**
 * Pure SVG builders for the downloadable certificate and badge emblems.
 * Self-contained: hard-coded brand colours + system fonts, explicit width/height,
 * so they render identically on-page and when rasterised to PNG.
 */

const C = {
  emerald: "#059669",
  emeraldLight: "#10b981",
  blue: "#2563eb",
  blueLight: "#3b82f6",
  ink: "#0f172a",
  slate: "#475569",
  muted: "#64748b",
  border: "#e2e8f0",
  faint: "#f8fafc",
  paper: "#ffffff",
};
const FONT = "'Segoe UI', system-ui, -apple-system, Helvetica, Arial, sans-serif";
const SERIF = "Georgia, 'Times New Roman', serif";

function esc(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function star(cx: number, cy: number, outer: number, inner: number, points = 5): string {
  let d = "";
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outer : inner;
    const a = (Math.PI / points) * i - Math.PI / 2;
    d += (i === 0 ? "M" : "L") + (cx + r * Math.cos(a)).toFixed(1) + "," + (cy + r * Math.sin(a)).toFixed(1);
  }
  return d + "Z";
}

export interface CertificateData {
  name: string;
  rank: string;
  level: number;
  badges: number;
  badgeTotal: number;
  pathways: number;
  diversity: number;
  date: string;
  id: string;
}

export function certificateSvg(d: CertificateData): string {
  const W = 1200;
  const H = 849;
  const name = esc(d.name.trim() || "D.R.O.N.A. Explorer");
  const stats = [
    { v: `${d.level}`, l: "RANK LEVEL" },
    { v: `${d.badges}/${d.badgeTotal}`, l: "BADGES" },
    { v: `${d.pathways}`, l: "PATHWAYS EXPLORED" },
    { v: `${d.diversity}`, l: "EVIDENCE DIVERSITY" },
  ];
  const colW = 240;
  const startX = W / 2 - (colW * stats.length) / 2 + colW / 2;
  const statsSvg = stats
    .map((s, i) => {
      const x = startX + i * colW;
      const divider =
        i < stats.length - 1
          ? `<line x1="${x + colW / 2}" y1="548" x2="${x + colW / 2}" y2="612" stroke="${C.border}" stroke-width="1.5"/>`
          : "";
      return `
        <text x="${x}" y="588" text-anchor="middle" font-family="${FONT}" font-size="38" font-weight="800" fill="${C.ink}">${esc(s.v)}</text>
        <text x="${x}" y="616" text-anchor="middle" font-family="${FONT}" font-size="13" letter-spacing="1.5" fill="${C.muted}">${s.l}</text>
        ${divider}`;
    })
    .join("");

  // Seal (bottom-right)
  const sx = 1000;
  const sy = 690;
  const seal = `
    <g>
      <circle cx="${sx}" cy="${sy}" r="64" fill="url(#sealGrad)"/>
      <circle cx="${sx}" cy="${sy}" r="64" fill="none" stroke="#ffffff" stroke-width="2" stroke-opacity="0.35"/>
      <circle cx="${sx}" cy="${sy}" r="50" fill="none" stroke="#ffffff" stroke-width="1.5" stroke-opacity="0.55"/>
      <path d="${star(sx, sy - 6, 20, 8)}" fill="#ffffff"/>
      <text x="${sx}" y="${sy + 30}" text-anchor="middle" font-family="${FONT}" font-size="11" font-weight="700" letter-spacing="2" fill="#ffffff">VERIFIED</text>
    </g>`;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="frameGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${C.emerald}"/>
      <stop offset="100%" stop-color="${C.blue}"/>
    </linearGradient>
    <linearGradient id="logoGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${C.emeraldLight}"/>
      <stop offset="100%" stop-color="${C.blue}"/>
    </linearGradient>
    <linearGradient id="sealGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${C.emerald}"/>
      <stop offset="100%" stop-color="${C.blue}"/>
    </linearGradient>
    <linearGradient id="ruleGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="${C.emerald}"/>
      <stop offset="100%" stop-color="${C.blue}"/>
    </linearGradient>
  </defs>

  <rect width="${W}" height="${H}" rx="20" fill="${C.paper}"/>
  <rect x="3" y="3" width="${W - 6}" height="${H - 6}" rx="18" fill="${C.faint}"/>
  <rect x="22" y="22" width="${W - 44}" height="${H - 44}" rx="14" fill="${C.paper}" stroke="url(#frameGrad)" stroke-width="3"/>
  <rect x="22" y="22" width="${W - 44}" height="7" rx="3.5" fill="url(#frameGrad)"/>

  <!-- header -->
  <g transform="translate(${W / 2 - 118}, 64)">
    <rect x="0" y="0" width="44" height="44" rx="12" fill="url(#logoGrad)"/>
    <circle cx="15" cy="20" r="4" fill="#ffffff"/>
    <circle cx="29" cy="20" r="4" fill="#ffffff"/>
    <rect x="14" y="30" width="16" height="3" rx="1.5" fill="#ffffff" opacity="0.85"/>
    <text x="58" y="22" font-family="${FONT}" font-size="22" font-weight="800" letter-spacing="1" fill="${C.ink}">D.R.O.N.A.</text>
    <text x="58" y="40" font-family="${FONT}" font-size="12" letter-spacing="1.5" fill="${C.muted}">ROBOTIC ACADEMIC ADVISOR</text>
  </g>

  <text x="${W / 2}" y="196" text-anchor="middle" font-family="${FONT}" font-size="15" font-weight="700" letter-spacing="5" fill="${C.emerald}">CERTIFICATE OF CAREER EXPLORATION</text>
  <text x="${W / 2}" y="246" text-anchor="middle" font-family="${FONT}" font-size="17" fill="${C.muted}">This certifies that</text>

  <text x="${W / 2}" y="332" text-anchor="middle" font-family="${SERIF}" font-size="58" font-weight="700" fill="${C.ink}">${name}</text>
  <rect x="${W / 2 - 150}" y="352" width="300" height="4" rx="2" fill="url(#ruleGrad)"/>

  <text x="${W / 2}" y="408" text-anchor="middle" font-family="${FONT}" font-size="18" fill="${C.slate}">has completed a bias-aware, evidence-grounded career exploration with D.R.O.N.A.,</text>
  <text x="${W / 2}" y="436" text-anchor="middle" font-family="${FONT}" font-size="18" fill="${C.slate}">reaching the rank of <tspan font-weight="700" fill="${C.ink}">${esc(d.rank)}</tspan> by exploring widely and checking the evidence.</text>

  <rect x="170" y="510" width="860" height="120" rx="16" fill="${C.faint}" stroke="${C.border}" stroke-width="1.5"/>
  ${statsSvg}

  ${seal}

  <!-- footer -->
  <text x="80" y="700" font-family="${FONT}" font-size="14" fill="${C.muted}">Issued ${esc(d.date)}</text>
  <text x="80" y="722" font-family="${FONT}" font-size="12" fill="${C.muted}">Verification ID  ${esc(d.id)}</text>
  <text x="80" y="772" font-family="${SERIF}" font-size="26" font-style="italic" fill="${C.ink}">D.R.O.N.A.</text>
  <rect x="80" y="784" width="220" height="2" fill="${C.border}"/>
  <text x="80" y="804" font-family="${FONT}" font-size="12" letter-spacing="1" fill="${C.muted}">Softwarica College of IT and E-Commerce</text>
</svg>`;
}

// ── Badge emblem ──────────────────────────────────────────────────────────────

export function badgeEmblemSvg(title: string, blurb: string, earned: boolean): string {
  const S = 600;
  const cx = S / 2;
  const cy = 250;
  const ring = earned ? "url(#bgGrad)" : "#cbd5e1";
  const inner = earned ? "#ffffff" : "#f1f5f9";
  const ink = earned ? C.ink : "#94a3b8";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${S}" height="${S}" viewBox="0 0 ${S} ${S}">
  <defs>
    <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${C.emeraldLight}"/>
      <stop offset="100%" stop-color="${C.blue}"/>
    </linearGradient>
  </defs>
  <rect width="${S}" height="${S}" rx="28" fill="${C.paper}"/>
  <rect x="3" y="3" width="${S - 6}" height="${S - 6}" rx="26" fill="none" stroke="${C.border}" stroke-width="2"/>

  <!-- medallion -->
  <circle cx="${cx}" cy="${cy}" r="150" fill="${ring}"/>
  <circle cx="${cx}" cy="${cy}" r="150" fill="none" stroke="#ffffff" stroke-width="3" stroke-opacity="0.35"/>
  <circle cx="${cx}" cy="${cy}" r="116" fill="${inner}"/>
  <path d="${star(cx, cy - 4, 64, 26)}" fill="${earned ? "url(#bgGrad)" : "#cbd5e1"}"/>
  <text x="${cx}" y="${cy + 92}" text-anchor="middle" font-family="${FONT}" font-size="15" font-weight="700" letter-spacing="3" fill="${earned ? C.emerald : "#94a3b8"}">${earned ? "EARNED" : "LOCKED"}</text>

  <text x="${cx}" y="470" text-anchor="middle" font-family="${FONT}" font-size="34" font-weight="800" fill="${ink}">${esc(title)}</text>
  <text x="${cx}" y="506" text-anchor="middle" font-family="${FONT}" font-size="16" fill="${C.muted}">${esc(blurb).slice(0, 60)}</text>
  <text x="${cx}" y="560" text-anchor="middle" font-family="${FONT}" font-size="13" letter-spacing="2" fill="${C.muted}">D.R.O.N.A.  ·  EXPLORATION BADGE</text>
</svg>`;
}
