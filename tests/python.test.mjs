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

// Selection changes drawing only, preserving full-floor calculations.
const selectionInfo = await call({ type: 'upload', csv: first });
const pid = selectionInfo.plans[0];
assert.equal(selectionInfo.apartments[pid].length, 5);
const uid = selectionInfo.apartments[pid][0];
for (const chart of ['overview', 'attributes', 'apartments', 'orientation', 'openings']) {
  const all = await call({ type: 'render', chart, plan: pid });
  const selected = await call({ type: 'render', chart, plan: pid, apartment: uid });
  assert.notEqual(selected.png, all.png);
  const restored = await call({ type: 'render', chart, plan: pid, apartment: '' });
  assert.equal(restored.png, all.png, `${chart}: All apartments restores original output`);
}
py.globals.set('selected_plan', pid); py.globals.set('selected_unit', uid);
await py.runPythonAsync(`
import apartments, attributes, orientation, openings, overview
from matplotlib.colors import to_rgba
cached = model.build_plan(selected_plan)
expected = sum(r['unit_id'] != selected_unit for r in cached['rooms'].values())
for module in [apartments, attributes, orientation, openings, overview]:
    fig = module.render(selected_plan, apartment_id=selected_unit)
    gray = sum(p.get_facecolor()[:3] == to_rgba('lightgray')[:3] for p in fig.axes[0].patches)
    assert gray >= expected, (module.__name__, gray, expected)
    labels = {t.get_text() for t in fig.axes[0].texts}
    for n, room in cached['rooms'].items():
        if room['unit_id'] != selected_unit:
            assert not any(t == f'R{n}' or t.startswith(f'R{n}\\n') for t in labels)
    assert model.build_plan(selected_plan) is cached
    bridge.plt.close('all')
`);
await assert.rejects(call({ type: 'render', chart: 'apartments', plan: pid, apartment: 'unknown' }), /apartment is not/);
const statsAll = await call({ type: 'render', chart: 'room_types', plan: pid });
const statsSelected = await call({ type: 'render', chart: 'room_types', plan: pid, apartment: uid });
assert.equal(statsAll.png, statsSelected.png);
console.log('PASS: apartment selection, gray context, hidden labels, restored all-apartment plots, unchanged cache and statistics.');

const heightInfo = await call({ type: 'upload', csv: first });
const originalHeight = heightInfo.window_heights[0].value;
const beforeHeightPlots = {};
for (const chart of ['attributes', 'window_heights', 'wwr_distribution', 'wwr_by_type', 'openings']) {
  beforeHeightPlots[chart] = (await call({ type: 'render', chart })).png;
}
await py.runPythonAsync('before_edit = model.df.copy(deep=True)');
const changedHeight = await call({ type: 'window_height', original: originalHeight, height: 0.25 });
assert(changedHeight.window_heights.some(group => group.value === 0.25));
assert.equal(await py.runPythonAsync('len(model._cache)'), 0);
await py.runPythonAsync("non_windows = ~model.df.entity_subtype_n.str.contains('WINDOW')\nassert model.df.loc[non_windows].equals(before_edit.loc[non_windows])");
for (const chart of Object.keys(beforeHeightPlots)) {
  const after = (await call({ type: 'render', chart })).png;
  if (chart === 'openings') assert.equal(after, beforeHeightPlots[chart]);
  else assert.notEqual(after, beforeHeightPlots[chart], `${chart} responds to height edits`);
}
for (const height of [0, -1, null, 'bad', true]) {
  await assert.rejects(call({ type: 'window_height', original: 0.25, height }), /greater than zero/);
}
await assert.rejects(call({ type: 'window_height', original: 12345, height: 1 }), /No windows/);
assert.deepEqual((await call({ type: 'upload', csv: first })).window_heights, heightInfo.window_heights);
await call({ type: 'upload', csv: noWindows });
await assert.rejects(call({ type: 'window_height', original: null, height: 1 }), /No windows/);
console.log('PASS: height editing, updated plots, unchanged non-window rows, validation, and upload reset.');
