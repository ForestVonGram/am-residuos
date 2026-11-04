const { copyFileSync } = require('node:fs');
const { resolve } = require('node:path');

const source = require.resolve('maplibre-gl/dist/maplibre-gl-worker.mjs');
const destination = resolve(__dirname, '../public/maplibre-gl-worker.js');

copyFileSync(source, destination);
