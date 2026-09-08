import { charts } from './charts.js';
let runtime;
let chain = Promise.resolve();
const base = `${import.meta.env.BASE_URL}python/`;
async function init() {
  if (runtime) return runtime;
  postMessage({ progress: 'Loading Python in your browser…' });
  const { loadPyodide } = await import(/* @vite-ignore */ 'https://cdn.jsdelivr.net/pyodide/v314.0.6/full/pyodide.mjs');
  const py = await loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v314.0.6/full/' });
  postMessage({ progress: 'Loading geometry and plotting libraries…' });
  await py.loadPackage(['pandas', 'shapely', 'matplotlib']);
  py.FS.mkdirTree('/app');
  await Promise.all(['model', 'bridge', ...charts.map(([id]) => id)].map(async name => {
    const response = await fetch(`${base}${name}.py`);
    if (!response.ok) throw new Error(`Could not load ${name}.py`);
    py.FS.writeFile(`/app/${name}.py`, await response.text());
  }));
  await py.runPythonAsync("import sys, matplotlib\nmatplotlib.use('Agg')\nsys.path.insert(0, '/app')\nimport bridge");
  runtime = py;
  return py;
}
self.onmessage = ({ data }) => {
  chain = chain.then(async () => {
    try {
      const py = await init();
      if (data.type === 'init') { postMessage({ id: data.id, result: true }); return; }
      const started = performance.now();
      py.globals.set('request_json', JSON.stringify(data));
      try {
        const result = JSON.parse(await py.runPythonAsync('bridge.handle(request_json)'));
        postMessage({ id: data.id, result, seconds: (performance.now() - started) / 1000 });
      } finally { py.globals.delete('request_json'); }
    } catch (error) {
      postMessage({ id: data.id, error: error.message });
    }
  });
};
