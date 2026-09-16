/* Medallion toggle — static analysis of the wiring between
   index.html, portfolio.js and portfolio.css (no browser needed). */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "flaskblog", "static");
const js = fs.readFileSync(path.join(root, "js", "portfolio.js"), "utf8");
const css = fs.readFileSync(path.join(root, "css", "portfolio.css"), "utf8");
const html = fs.readFileSync(
  path.join(__dirname, "flaskblog", "templates", "index.html"),
  "utf8"
);

const checks = [];
const check = (name, cond) => checks.push([name, !!cond]);

/* HTML side */
check("medallion button exists in HTML", /id="dm-medallion"/.test(html));
check("medallion has both glyphs", /dm-medallion-glyph tech/.test(html) && /dm-medallion-glyph art/.test(html));
check("medallion exposes aria-pressed", /aria-pressed/.test(html));
check("medallion inside the dm-root", /id="dm-root"[\s\S]*id="dm-medallion"/.test(html));
check("both mode layers exist", /id="mode-technical"/.test(html) && /mode-creative/.test(html));

/* JS side: a click on the medallion must flip the mode */
check("JS binds a listener on #dm-medallion", /dm-medallion[\s\S]{0,400}addEventListener\s*\(\s*["']click["']/.test(js));
check("JS flips the aria-pressed state", /aria-pressed/.test(js));
check("JS calls applyMode (the actual flip)", /applyMode\s*\(/.test(js));
check("applyMode switches both layers", /mode-technical/.test(js) && /mode-creative/.test(js));
check("JS persists the chosen side", /localStorage/.test(js));
check("JS honours prefers-reduced-motion", /prefers-reduced-motion|reducedMotion/.test(js));

/* CSS side: the toggle styling */
check("medallion styles exist", /\.dm-medallion\s*\{/.test(css));
check("medallion ring styled", /dm-medallion-ring/.test(css));
check("medallion glyph styles", /dm-medallion-glyph/.test(css));
check("mode classes for both sides", /\.mode-technical/.test(css) && /\.mode-creative/.test(css));
check("creative side uses warm palette not green", !/#(7ee787|3fb950)\b/i.test(css));

let failed = 0;
for (const [name, ok] of checks) {
  if (!ok) { failed++; console.log("FAIL:", name); }
}
console.log(failed === 0 ? "MEDALLION_ALL_PASS (" + checks.length + " checks)" : failed + " failed of " + checks.length);
process.exit(failed === 0 ? 0 : 1);
