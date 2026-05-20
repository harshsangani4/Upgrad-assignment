// Style lockdown (Phase 12.6.3). Pure Node (no grep) so it runs on any OS.
// Fails non-zero if any rogue value is found in frontend/src (except theme.ts).
const fs = require("node:fs");
const path = require("node:path");

const SRC = path.join(__dirname, "..", "src");
const EXCLUDE = new Set(["theme.ts"]);
const EXTS = new Set([".ts", ".tsx", ".css"]);

const CHECKS = [
  { name: "hex literals", re: /#[0-9a-fA-F]{3,6}\b/ },
  { name: "rgba/rgb literals", re: /\brgba?\(/ },
  {
    name: "off-scale spacing",
    re: /\b(p|m|gap|space|pt|pb|pl|pr|px|py|mt|mb|ml|mr|mx|my)-(5|7|9|10|11|13|14|15|17|18|19|20|21|22|23)\b/,
  },
];

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (EXTS.has(path.extname(entry.name)) && !EXCLUDE.has(entry.name)) out.push(full);
  }
  return out;
}

let failed = false;
const files = walk(SRC);
for (const check of CHECKS) {
  const hits = [];
  for (const file of files) {
    const lines = fs.readFileSync(file, "utf8").split("\n");
    lines.forEach((line, i) => {
      if (check.re.test(line)) hits.push(`${path.relative(SRC, file)}:${i + 1}: ${line.trim()}`);
    });
  }
  if (hits.length) {
    console.error(`✗ ${check.name} (${hits.length}):\n  ${hits.join("\n  ")}\n`);
    failed = true;
  } else {
    console.log(`✓ ${check.name}`);
  }
}

process.exit(failed ? 1 : 0);
