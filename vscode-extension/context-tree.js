'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');

async function safeFile(root, relative) {
  if (typeof relative !== 'string' || path.isAbsolute(relative)) throw new Error('Referência de arquivo inválida.');
  const base = await fs.realpath(root);
  const target = await fs.realpath(path.resolve(base, relative));
  const rel = path.relative(base, target);
  if (!rel || rel.startsWith('..' + path.sep) || rel === '..' || path.isAbsolute(rel)) throw new Error('Arquivo fora do projeto.');
  if (!(await fs.stat(target)).isFile()) throw new Error('Referência não é arquivo.');
  return target;
}
function fileNode(label, root, source) {
  return {label, root, source, description:source.role || '', children:[]};
}
function textGroup(label, values = []) {
  return {label, children:values.map(value => ({label:value, children:[]}))};
}
function specificationNodes(contract) {
  const spec = contract.specification;
  if(!spec) return [];
  const model = spec.data_model || {};
  return [{label:'Conceito e especificação',children:[
    {label:'Intenção: ' + contract.intent,children:[]},
    textGroup('Limites',contract.boundaries),textGroup('Exclusões',spec.exclusions),textGroup('Atores',spec.actors),
    ...(spec.use_cases || []).map(use => ({label:`${use.id}: ${use.title}`,description:use.actor,children:[
      textGroup('Pré-condições',use.preconditions),textGroup('Fluxo principal',use.main_flow),
      textGroup('Alternativas e falhas',use.alternatives),textGroup('Pós-condições',use.postconditions),textGroup('Regras',use.rules)
    ]})),
    {label:'Modelo de dados',children:[
      ...(model.entities || []).map(entity => ({label:entity.name,children:[textGroup('Atributos',entity.attributes),textGroup('Integridade',entity.invariants)]})),
      ...(model.relationships || []).map(rel => ({label:`${rel.from} → ${rel.to} (${rel.cardinality})`,children:[textGroup('Integridade',rel.invariants)]}))
    ]}
  ]}];
}
function projectNodes(root, data) {
  return [
    ...(data.warnings || []).map(label => ({label:'Aviso: ' + label, children:[]})),
    ...(data.contracts || []).map(contract => ({
      label:contract.title || contract.id, description:contract.status || '', root, contract,
      children:[
        fileNode('Contrato aprovado / definição', root, {path:`.centaur/contracts/${contract.id}/v${String(contract.version).padStart(3,'0')}.json`}),
        ...(contract.rules || []).map(rule => ({
          label:`${rule.id}: ${rule.description}`, description:`${rule.kind === 'non_functional' ? 'RNF' : 'RF'} · ${rule.verification}`, root, contract, rule,
          children:[
            {label:'Aceite: ' + JSON.stringify(rule.acceptance), children:[]},
            ...(rule.sources || []).map(source => fileNode(`${source.role}: ${source.path}:${source.start}`, root, source)),
            ...(rule.evidence || []).map(e => fileNode(`Evidência: ${e.verification} · ${e.summary}`,root,e)),
            ...(rule.issues || []).map(label => ({label,children:[]}))
          ]
        })),
        ...specificationNodes(contract),
        ...(data.use_cases || []).filter(flow => flow.contract === contract.id).map(flow => ({
          label:'Fluxo: ' + flow.title, children:flow.nodes.map(step => ({label:step.label,description:step.detail,children:[]}))
        }))
      ]
    }))
  ];
}
function relatedContext(data, relative) {
  return (data?.contracts || []).flatMap(contract => (contract.rules || [])
    .filter(rule => (rule.sources || []).some(source => source.path === relative))
    .map(rule => ({contract:contract.id,intent:contract.intent,boundaries:contract.boundaries,kind:rule.kind || 'functional',rule:rule.id,description:rule.description,acceptance:rule.acceptance,specification:contract.specification}))).slice(0,8);
}
module.exports = {safeFile, projectNodes, relatedContext};
