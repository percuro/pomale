// Writes the app icons in public/ from src/app/icon.svg (512 × 512, full bleed, the motif
// inside the middle 80 % so that a round mask does not cut it) and the notification badge
// from src/app/badge.svg. Needs rsvg-convert (librsvg).
//   node scripts/icons.mjs
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const path = (relative) => fileURLToPath(new URL(relative, import.meta.url));
const source = readFileSync(path('../src/app/icon.svg'), 'utf8');

// Browsers and "any" icons get rounded corners; maskable and Apple icons stay full bleed,
// the system cuts its own shape
const body = source.replace(/<!--[\s\S]*?-->/g, '').replace(/^[\s\S]*?<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '');
const rounded = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <clipPath id="shape"><rect width="512" height="512" rx="112"/></clipPath>
  <g clip-path="url(#shape)">${body}</g>
</svg>
`;
writeFileSync(path('../public/icon.svg'), rounded);

const png = (svg, size, file) => {
  execFileSync('rsvg-convert', ['-w', String(size), '-h', String(size), '-o', path(`../public/${file}`)], { input: svg });
  console.log(file);
};
png(rounded, 192, 'icon-192.png');
png(rounded, 512, 'icon-512.png');
png(source, 512, 'icon-maskable-512.png');
png(source, 180, 'apple-touch-icon.png');
png(readFileSync(path('../src/app/badge.svg'), 'utf8'), 96, 'badge-96.png');
