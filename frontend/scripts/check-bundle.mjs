// Size budget of the built frontend (run after `npm run build`): fails when the code an app start
// loads, or any single chunk, grows past its limit. Sizes are minified, before compression.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';

const DIST = new URL('../dist/', import.meta.url).pathname;
// What index.html loads at once: the entry chunk and the chunks it imports statically
const START_LIMIT_KB = 480;
// Vite's own warning limit; no chunk may come near it again
const CHUNK_LIMIT_KB = 400;

const kb = (bytes) => bytes / 1000;
const html = readFileSync(join(DIST, 'index.html'), 'utf8');
const startFiles = [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.js)"/g)].map((match) => match[1]);
const assets = readdirSync(join(DIST, 'assets')).filter((name) => name.endsWith('.js'));

let failed = false;
const startBytes = startFiles.reduce((sum, file) => sum + statSync(join(DIST, file)).size, 0);
const startGzip = startFiles.reduce((sum, file) => sum + gzipSync(readFileSync(join(DIST, file))).length, 0);
console.log(`App start: ${kb(startBytes).toFixed(1)} kB (gzip ${kb(startGzip).toFixed(1)} kB) in ${startFiles.length} files`);
if (kb(startBytes) > START_LIMIT_KB) {
  console.error(`  over the budget of ${START_LIMIT_KB} kB: ${startFiles.join(', ')}`);
  failed = true;
}
for (const name of assets) {
  const size = kb(statSync(join(DIST, 'assets', name)).size);
  if (size > CHUNK_LIMIT_KB) {
    console.error(`Chunk ${name}: ${size.toFixed(1)} kB, over the limit of ${CHUNK_LIMIT_KB} kB`);
    failed = true;
  }
}
const precached = /\.(js|css|html|svg|png|webmanifest)$/;
const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? walk(join(dir, entry.name)) : [join(dir, entry.name)],
  );
const offline = walk(DIST)
  .filter((file) => precached.test(file) && !/\/sw\.js$/.test(file))
  .reduce((sum, file) => sum + statSync(file).size, 0);
console.log(`Offline copy (service worker precache): about ${kb(offline).toFixed(0)} kB`);
process.exit(failed ? 1 : 0);
