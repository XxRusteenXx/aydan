// Tests the same WebAssembly Python distribution used by the browser worker.
import { loadPyodide } from 'pyodide';
import { readFile, readdir, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { charts } from '../src/charts.js';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const started = performance.now();
const cache = path.join(root, '.test-cache');
await mkdir(cache, { recursive: true });
const py = await loadPyodide({ packageCacheDir: cache });
await py.loadPackage(['pandas', 'shapely', 'matplotlib']);
py.FS.mkdirTree('/app');
for (const name of await readdir(path.join(root, 'public/python'))) {
  if (name.endsWith('.py')) py.FS.writeFile(`/app/${name}`, await readFile(path.join(root, 'public/python', name), 'utf8'));
}
await py.runPythonAsync("import sys, matplotlib\nmatplotlib.use('Agg')\nsys.path.insert(0, '/app')\nimport bridge, model");
console.log(`Runtime initialized: ${((performance.now() - started) / 1000).toFixed(1)}s`);
async function call(data) {
  py.globals.set('payload', JSON.stringify(data));
  try { return JSON.parse(await py.runPythonAsync('bridge.handle(payload)')); }
  finally { py.globals.delete('payload'); }
}
for (const [file, rooms, units] of [['floor_1588.csv', 21, 2], ['floor_9705.csv', 55, 5], ['floor_9706.csv', 55, 5]]) {
  const csv = await readFile(path.join(root, '../floor', file), 'utf8');
  const info = await call({ type: 'upload', csv });
  assert.equal(info.rooms, rooms); assert.equal(info.units, units); assert.equal(info.plans.length, 1);
  for (const [chart] of charts) {
    const start = performance.now();
    const result = await call({ type: 'render', chart, plan: info.plans[0] });
    const png = Buffer.from(result.png, 'base64');
    assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
    assert(png.length > 5000);
    if (file === 'floor_1588.csv') await writeFile(path.join(cache, `${chart}.png`), png);
    console.log(`${file} ${chart}: ${((performance.now() - start) / 1000).toFixed(2)}s (${png.length} bytes)`);
  }
  assert.equal(await py.runPythonAsync('len(model._cache)'), 1, 'Plan calculations are cached');
}
await assert.rejects(call({ type: 'render', chart: '../model' }), /Unknown visualization/);
await assert.rejects(call({ type: 'render', chart: 'attributes', plan: 'does-not-exist' }), /not in the uploaded/);
await assert.rejects(call({ type: 'upload', csv: 'foo,bar\n1,2\n' }), /Missing CSV columns/);
await assert.rejects(call({ type: 'render', chart: 'overview' }), /Load a floor CSV first/);
const first = await readFile(path.join(root, '../floor/floor_9705.csv'), 'utf8');
const second = await readFile(path.join(root, '../floor/floor_9706.csv'), 'utf8');
await assert.rejects(call({ type: 'upload', csv: first.trimEnd() + '\n' + second.slice(second.indexOf('\n') + 1) }), /exactly one floor/);
py.globals.set('original', first);
const noWindows = await py.runPythonAsync("import io\nx = model.pd.read_csv(io.StringIO(original), dtype=str)\nx = x[~x.entity_subtype.fillna('').str.contains('WINDOW')]\nx.to_csv(index=False)");
const info = await call({ type: 'upload', csv: noWindows });
for (const chart of ['orientation', 'openings', 'window_heights', 'wwr_distribution']) {
  assert((await call({ type: 'render', chart, plan: info.plans[0] })).png.length > 1000);
}
console.log('PASS: all 30 example plots, cached plans, missing columns, multiple floors, invalid selections, and a floor without windows.');
