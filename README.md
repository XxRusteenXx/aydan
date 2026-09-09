# Floor CSV viewer

Minimal React app with **no application backend**. Python runs in a Web Worker through Pyodide/WebAssembly. CSV contents stay in browser memory; resetting Python or closing the page clears them. Network requests download only the app, Python runtime, and packages.

## Run

Install Node.js 20.19+ or 22.12+, then from this directory:

```sh
npm install
npm run dev
```

Open the local address printed by Vite (normally http://localhost:5173). Choose a CSV from the repository's `floor` folder. The initial download may take tens of seconds. Click **Load floor**, choose a visualization. Changes to the visualization, plan, apartment, or attribute redraw the plot automatically. Download the resulting PNG if needed.

Node/Vite only serves static frontend files during development. It never receives the CSV and never launches Python. A Python installation is not required.

## Build and host

```sh
npm run build
npm run preview
```

Deploy `dist/` to a static website host. Serve over HTTP(S), not by opening index.html with file://. The app loads Pyodide 314.0.6 and its pandas, Shapely, and Matplotlib packages from jsDelivr. Internet access is needed for the first load; this is not a fully offline app. The worker is a module worker. Use a current Chrome, Edge, Firefox, or Safari.

## Files and data flow

* `src/main.jsx`: React upload, plan/plot selection, status, download, and reset controls.
* `src/python.worker.js`: initializes Python once, copies Python modules into its virtual filesystem, exchanges JSON messages with React.
* `public/python/model.py`: validates one-floor CSV, parses geometry, caches calculated plans.
* `public/python/bridge.py`: dispatches only known plot names; converts Matplotlib figures to base64 PNG in memory.
* `public/python/overview.py`: floor overview (up to four plans).
* `public/python/attributes.py`: room attribute map.
* `public/python/apartments.py`: apartment segmentation.
* `public/python/orientation.py`: window direction arrows.
* `public/python/openings.py`: actual window/door polygons.
* `public/python/room_types.py`: room counts by type.
* `public/python/ceiling_heights.py`: room ceiling-height histogram.
* `public/python/window_heights.py`: window head-height histogram.
* `public/python/wwr_distribution.py`: all-floor WWR histogram.
* `public/python/wwr_by_type.py`: mean WWR by room type.

React sends `{type: 'upload', csv: text}` to the worker. Python retains a DataFrame and returns a floor summary. React subsequently sends `{type: 'render', chart, plan, attribute}`; Python returns `{png: base64}`. No CSV file is written to persistent storage, no pickle is used, and no neural network executes. Python modules are separate frontend assets, fetched once during initialization.

## Input

Comma-separated UTF-8 CSV, at most 10 MB / 20,000 rows / 5,000 room and opening records. Required columns: `building_id`, `floor_id`, `plan_id`, `unit_id`, `unit_usage`, `entity_type`, `entity_subtype`, `geom`, `elevation`, `height`, `roomtype`. Extra columns are ignored. Exactly one building and floor are accepted; multiple plan IDs on that floor are supported. Relevant geometry must be valid, nonempty Polygon WKT. Numeric IDs stay strings. Missing or nonnumeric heights are treated as missing, using v1 defaults where applicable.

Floor statistics use all plans in the file rather than dataset sampling. Layout views select a plan. Room numbers are local display indices; apartment colors derive from `unit_id`. The five layout plots have an Apartment selector (CSV unit IDs), defaulting to All apartments. Selecting a unit redraws the plot with other rooms in gray, without changing cached calculations. Statistics remain floor-wide. Plan or visualization changes reset the selector. Room filtering and parameter editing are not implemented.

## Inherited calculation limitations

The layout functions were extracted from `Data Visualisation Code_v1.ipynb` using `extract_notebook.py`. WWR uses bounding-box dimensions, capped at 1; it is not a measured exterior-wall ratio. Adjacency heuristics may interpret shared solid walls as passages. Only the largest associated window is used for each room's orientation marker. Disconnected footprints keep the largest component. Height histograms use the original 0–6 m filter. These are research visualizations, not independently validated physical models.

## Verification

`npm test` uses the same WebAssembly Python version as the browser. It renders all ten plots for all three floor examples, checks PNG output and expected room/unit counts, confirms plan caching, and covers invalid uploads and no-window data. It downloads scientific packages into `.test-cache` on its first run. This test uses Node only as a test harness; the shipped application is entirely browser-side.

The notebook extraction script is a historical development helper and is not run by the app. Do not rerun it on the working app: it overwrites the extracted model and five layout modules, including the later apartment-selection changes.
