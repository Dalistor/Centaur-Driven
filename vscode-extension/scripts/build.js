const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const source = path.join(root, 'centaur-driven-graphify/scripts');
const target = path.join(__dirname, '../dist/engine');
fs.rmSync(target, { recursive: true, force: true });
fs.mkdirSync(target, { recursive: true });
for (const file of ['volante.py', 'render-volante.py', 'volante-template.html']) {
  fs.copyFileSync(path.join(source, file), path.join(target, file));
}
console.log('Engine e painel do Volante incluídos na extensão.');
