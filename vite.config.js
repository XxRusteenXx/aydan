import { defineConfig } from 'vite';

// Pyodide's runtime loads ES modules, including inside the production worker.
export default defineConfig({ worker: { format: 'es' } });
