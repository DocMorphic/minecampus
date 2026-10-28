// Select only this bundle's runtime; preserve all existing player settings.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
function configure(root, executable = process.execPath) {
  const file = path.join(root, 'data/instances/minecampus/.minecraft/config/realworldmc.json');
  const config = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    throw new Error('The campus settings file is invalid; no settings were changed.');
  }
  if (config.nodeExecutable === executable) return;
  config.nodeExecutable = executable;
  const pending = file + '.' + process.pid + '.pending';
  let created = false;
  try {
    fs.writeFileSync(pending, JSON.stringify(config, null, 2) + '\n', {flag: 'wx', mode: 0o600});
    created = true;
    fs.renameSync(pending, file);
  } finally {
    if (created && fs.existsSync(pending)) fs.unlinkSync(pending);
  }
}
if (require.main === module) {
  try { configure(process.argv[2]); }
  catch (error) { console.error('Could not prepare Minecampus: ' + error.message); process.exitCode = 1; }
}
module.exports = {configure};
