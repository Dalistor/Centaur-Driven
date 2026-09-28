'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ID = /^[a-z][a-z0-9_-]*$/;
const STEP = /^[A-Za-z][A-Za-z0-9_-]{0,39}$/;
function assert(condition, reason) { if (!condition) throw new Error(reason); }
function validate(flow, contract) {
  assert(flow && typeof flow === 'object' && !Array.isArray(flow) && flow.schema === 1, 'Fluxo exige schema 1.');
  assert(flow.contract === contract.id && flow.version === contract.version && ID.test(flow.contract), 'Fluxo pertence a outro contrato ou versão.');
  for (const key of ['title', 'summary']) assert(typeof flow[key] === 'string' && flow[key].trim().length > 0 && flow[key].length <= 500, `Campo ${key} inválido.`);
  assert(Array.isArray(flow.nodes) && flow.nodes.length >= 1 && flow.nodes.length <= 32, 'Fluxo exige entre 1 e 32 passos.');
  assert(Array.isArray(flow.edges) && flow.edges.length <= 64, 'Fluxo excede 64 conexões.');
  const ids = new Set();
  for (const n of flow.nodes) {
    assert(n && typeof n.id === 'string' && STEP.test(n.id) && !ids.has(n.id), 'ID de passo inválido ou repetido.');
    ids.add(n.id);
    assert(['start', 'action', 'decision', 'end'].includes(n.kind), 'Tipo de passo inválido.');
    assert(typeof n.label === 'string' && n.label.trim() && n.label.length <= 120, 'Título de passo inválido.');
    assert(typeof (n.detail ?? '') === 'string' && (n.detail ?? '').length <= 500, 'Descrição de passo inválida.');
  }
  assert(flow.nodes.some(n => n.kind === 'start'), 'O fluxo exige um início.');
  const links = new Set();
  for (const e of flow.edges) {
    assert(e && ids.has(e.from) && ids.has(e.to) && e.from !== e.to, 'Conexão aponta a passo inexistente ou ao próprio passo.');
    assert(typeof (e.label ?? '') === 'string' && (e.label ?? '').length <= 80, 'Condição inválida.');
    const key = JSON.stringify([e.from, e.to, e.label ?? '']);
    assert(!links.has(key), 'Conexão duplicada.'); links.add(key);
  }
  return { schema:1, contract:flow.contract, version:flow.version, title:flow.title.trim(), summary:flow.summary.trim(), nodes:flow.nodes.map(n => ({id:n.id,kind:n.kind,label:n.label.trim(),detail:n.detail ?? ''})), edges:flow.edges.map(e => ({from:e.from,to:e.to,label:e.label ?? ''})) };
}
function hash(bytes) { return crypto.createHash('sha256').update(bytes).digest('hex'); }
async function saveFlow(root, flow, contract, expectedHash) {
  const value = validate(flow, contract);
  const dir = path.join(root, '.centaur', 'use-cases');
  const base = path.join(root, '.centaur');
  await fs.promises.mkdir(dir, { recursive:true });
  for (const folder of [base, dir]) assert(!(await fs.promises.lstat(folder)).isSymbolicLink(), 'Pasta de casos de uso não pode ser um link simbólico.');
  const destination = path.join(dir, value.contract + '.json');
  let current = null;
  try { const st = await fs.promises.lstat(destination); assert(st.isFile() && !st.isSymbolicLink(), 'Arquivo de fluxo reservado ou link simbólico.'); current = await fs.promises.readFile(destination); } catch (e) { if (e.code !== 'ENOENT') throw e; }
  assert((current ? hash(current) : null) === expectedHash, 'O JSON mudou fora do painel. Reabra o Volante antes de salvar.');
  const text = JSON.stringify(value, null, 2) + '\n';
  assert(Buffer.byteLength(text) <= 100_000, 'Fluxo excede 100 KB.');
  const temporary = path.join(dir, `.${value.contract}-${crypto.randomUUID()}.tmp`);
  try { await fs.promises.writeFile(temporary, text, { flag:'wx' }); await fs.promises.rename(temporary, destination); } finally { await fs.promises.rm(temporary, {force:true}); }
  return {path:destination,hash:hash(Buffer.from(text))};
}
module.exports = { validate, saveFlow, hash };
