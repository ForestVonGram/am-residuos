const { existsSync, readFileSync } = require('node:fs');
const { resolve } = require('node:path');

const localEnvPath = resolve(__dirname, '../.env');
let configuredApiUrl = process.env.API_LOCAL_URL;

if (!configuredApiUrl && existsSync(localEnvPath)) {
  const apiUrlLine = readFileSync(localEnvPath, 'utf8')
    .split(/\r?\n/)
    .find((line) => /^\s*API_LOCAL_URL\s*=/.test(line));
  configuredApiUrl = apiUrlLine?.replace(/^\s*API_LOCAL_URL\s*=\s*/, '').trim();
  if (
    configuredApiUrl &&
    ((configuredApiUrl.startsWith('"') && configuredApiUrl.endsWith('"')) ||
      (configuredApiUrl.startsWith("'") && configuredApiUrl.endsWith("'")))
  ) {
    configuredApiUrl = configuredApiUrl.slice(1, -1);
  }
}

module.exports = {
  '/api': {
    target: configuredApiUrl || 'http://127.0.0.1:8000',
    secure: false,
    changeOrigin: true,
  },
};
