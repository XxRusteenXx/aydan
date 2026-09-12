import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { charts } from './charts.js';
import './style.css';

function App() {
  const worker = useRef(); const pending = useRef(new Map()); const nextId = useRef(0);
  const [status, setStatus] = useState('Starting Python…');
  const [ready, setReady] = useState(false); const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState(null); const [file, setFile] = useState(null);
  const [plan, setPlan] = useState(''); const [chart, setChart] = useState('overview');
  const [attribute, setAttribute] = useState('wwr'); const [plot, setPlot] = useState(null);
  const [session, setSession] = useState(0);
  const [apartment, setApartment] = useState('');
  const [heightGroup, setHeightGroup] = useState(0);
  const [windowHeight, setWindowHeight] = useState('');
  const heightMatters = ['attributes', 'orientation', 'window_heights', 'wwr_distribution', 'wwr_by_type'].includes(chart);
  function selectHeight(groups, index = 0) {
    setHeightGroup(index);
    setWindowHeight(groups[index]?.value ?? '');
  }
  async function applyWindowHeight(event) {
    event.preventDefault();
    const height = Number(windowHeight);
    if (windowHeight === '' || !Number.isFinite(height) || height <= 0) {
      setStatus('Window height must be a number greater than zero.'); return;
    }
    setBusy(true);
    try {
      const { result } = await request('window_height', { original: info.window_heights[heightGroup].value, height });
      setInfo(current => ({ ...current, ...result }));
      selectHeight(result.window_heights, result.window_heights.findIndex(group => group.value === height));
      await render();
    } catch (error) { setStatus(error.message); }
    finally { setBusy(false); }
  }
  const layout = ['overview', 'attributes', 'apartments', 'orientation', 'openings'].includes(chart);
  const apartmentOptions = !info ? [] : chart === 'overview'
    ? [...new Set(Object.values(info.apartments).flat())].sort()
    : info.apartments[plan] || [];
  function request(type, values = {}) {
    return new Promise((resolve, reject) => {
      const id = ++nextId.current;
      pending.current.set(id, { resolve, reject });
      worker.current.postMessage({ id, type, ...values });
    });
  }
  useEffect(() => {
    const w = new Worker(new URL('./python.worker.js', import.meta.url), { type: 'module' });
    worker.current = w;
    w.onmessage = ({ data }) => {
      if (data.progress) { setStatus(data.progress); return; }
      const task = pending.current.get(data.id);
      if (!task) return;
      pending.current.delete(data.id);
      data.error ? task.reject(new Error(data.error)) : task.resolve(data);
    };
    w.onerror = () => {
      setReady(false); setBusy(false);
      setStatus('Python could not start. Check your connection and click Reset Python to retry.');
      for (const task of pending.current.values()) task.reject(new Error('Python worker stopped.'));
      pending.current.clear();
    };
    request('init').then(() => { setReady(true); setStatus('Ready. Choose a floor CSV.'); })
      .catch(error => setStatus(`Initialization failed. Check your connection, then reset Python. ${error.message}`));
    return () => {
      w.terminate();
      // Outstanding requests belong to this discarded worker.
      pending.current.clear();
    };
  }, [session]);
  function reset() {
    worker.current?.terminate(); pending.current.clear();
    setReady(false); setBusy(false); setInfo(null); setPlot(null);
    setStatus('Restarting Python…'); setSession(value => value + 1);
  }
  async function render(selectedPlan = plan, selectedChart = chart, selectedApartment = apartment, selectedAttribute = attribute) {
    setBusy(true); setPlot(null); setStatus('Calculating and drawing…');
    try {
      const { result, seconds } = await request('render', { chart: selectedChart, plan: selectedPlan, attribute: selectedAttribute, apartment: selectedApartment });
      setPlot({ src: `data:image/png;base64,${result.png}`, label: charts.find(([id]) => id === selectedChart)[1] });
      setStatus(`Ready in ${seconds.toFixed(1)} seconds.`);
    } catch (error) { setStatus(error.message); }
    finally { setBusy(false); }
  }
  async function upload(event) {
    event.preventDefault(); if (!file) return;
    if (file.size > 10 * 1024 * 1024) { setStatus('Please choose a CSV smaller than 10 MB.'); return; }
    setBusy(true); setInfo(null); setPlot(null); setStatus('Checking your floor CSV…');
    try {
      const { result } = await request('upload', { csv: await file.text() });
      setInfo(result); setPlan(result.plans[0]); setApartment('');
      selectHeight(result.window_heights);
      await render(result.plans[0], chart, '');
    } catch (error) { setStatus(error.message); }
    finally { setBusy(false); }
  }
  const scope = charts.find(([id]) => id === chart)[2];
  return <main>
    <h1>Floor CSV viewer</h1>
    <p>Choose a floor CSV to view its plans, apartments, rooms, and windows. Your file stays in this browser.</p>
    <form onSubmit={upload}>
      <label htmlFor="csv">Floor CSV (up to 10 MB)</label>{' '}
      <input id="csv" type="file" accept=".csv,text/csv" disabled={busy} required onChange={event => setFile(event.target.files[0])} />
      <button disabled={!ready || busy || !file}>Load floor</button>
    </form>
    <p role="status" aria-live="polite" className="status">{status}</p>
    <button onClick={reset}>Reset Python / clear floor</button>
    {info && <>
      <p>Building {info.building_id} · Floor {info.floor_id} · {info.plans.length} plan(s) · {info.rooms} room/area records · {info.units} units</p>
      <section>
        <label htmlFor="chart">Visualization</label>{' '}
        <select id="chart" value={chart} disabled={busy} onChange={e => { setChart(e.target.value); setApartment(''); render(plan, e.target.value, ''); }}>{charts.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select>{' '}
        <label htmlFor="plan">Plan</label>{' '}
        <select id="plan" value={plan} disabled={busy || scope !== 'plan'} onChange={e => { setPlan(e.target.value); setApartment(''); render(e.target.value, chart, ''); }}>{info.plans.map(id => <option key={id}>{id}</option>)}</select>{' '}
        {layout && <><label htmlFor="apartment">Apartment</label>{' '}
          <select id="apartment" value={apartment} disabled={busy} onChange={e => { setApartment(e.target.value); render(plan, chart, e.target.value); }}>
            <option value="">All apartments</option>
            {apartmentOptions.map(id => <option key={id} value={id}>Apartment {id}</option>)}
          </select></>}
        {chart === 'attributes' && <><label htmlFor="attribute">Attribute</label>{' '}<select id="attribute" value={attribute} disabled={busy} onChange={e => { setAttribute(e.target.value); render(plan, chart, apartment, e.target.value); }}>
          <option value="wwr">Window-to-wall ratio</option><option value="room_area">Room area</option><option value="window_area">Window area</option><option value="ceiling_height">Ceiling height</option><option value="window_count">Window count</option>
        </select></>}
        <p>Scope: {scope === 'floor' ? 'entire uploaded floor' : 'selected plan'}.</p>
      </section>
      {heightMatters && <form onSubmit={applyWindowHeight}>
        {info.window_heights.length ? <>
          <label htmlFor="height-group">Current window height</label>{' '}
          <select id="height-group" value={heightGroup} disabled={busy} onChange={event => selectHeight(info.window_heights, Number(event.target.value))}>
            {info.window_heights.map((group, index) => <option key={index} value={index}>{group.value === null ? 'Missing in CSV' : `${group.value} m`} ({group.count} window records)</option>)}
          </select>{' '}
          <label htmlFor="window-height">New window height (m)</label>{' '}
          <input id="window-height" type="number" step="any" required value={windowHeight} disabled={busy} onChange={event => setWindowHeight(event.target.value)} />
          <button disabled={!ready || busy || windowHeight === '' || Number(windowHeight) <= 0}>Apply window height change</button>
          <p>Updates all window records with the selected height across the uploaded floor, including other plans and apartments. Changes stay in this browser; your original CSV is unchanged.</p>
        </> : <p>No windows in this floor to update.</p>}
      </form>}
      <details><summary>About these calculations</summary><p>These plots use the v1 notebook calculations. WWR is estimated from room bounding dimensions. Shared walls may be inferred as passages. Window arrows represent the largest associated window per room. Apartment colors are derived from unit_id; missing units appear as shared spaces. Height distributions exclude values outside 0–6 m. Footprints keep only the largest connected polygon.</p></details>
    </>}
    {plot && <figure><img src={plot.src} alt={plot.label} /><figcaption><a href={plot.src} download={`${chart}.png`}>Download plot</a></figcaption></figure>}
    <p className="note">First load downloads Python and scientific libraries. No Python installation or backend is required. Keep this tab open to retain the loaded floor.</p>
  </main>;
}
createRoot(document.getElementById('root')).render(<App />);
