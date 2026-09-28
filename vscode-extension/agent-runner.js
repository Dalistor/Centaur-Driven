'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {execFile, spawn} = require('node:child_process');
const {promisify} = require('node:util');
const crypto = require('node:crypto');
const exec = promisify(execFile);
const PROFILE_ID = /^[a-zA-Z][a-zA-Z0-9_-]{0,39}$/;
function validateProfile(profile) {
  if (!profile || !PROFILE_ID.test(profile.id) || typeof profile.label !== 'string' || !profile.label.trim() || profile.label.length > 80 || typeof profile.command !== 'string' || !profile.command.trim() || !Array.isArray(profile.args) || profile.args.length > 20 || !profile.args.every(x => typeof x === 'string' && x.length < 4000)) throw new Error('Perfil de agente inválido. Confira as configurações do Volante.');
  return profile;
}
function makePrompt(contract, rule, instruction) {
  if (typeof instruction !== 'string' || instruction.length > 1000) throw new Error('Instrução excede 1000 caracteres.');
  return `Contrato aprovado: ${contract.id}@${contract.version}. Regra: ${rule.key} — ${rule.description}.\nAceite: ${rule.acceptance.join('; ')}.\nLimites: ${(contract.boundaries||[]).join('; ')}.\nAutonomia: ${(contract.autonomy||[]).join('; ')}.\nInstrução humana: ${instruction.trim() || 'Implemente a regra conforme o contrato.'}\nTrabalhe neste worktree isolado. Revise o contrato e as fontes antes de agir. Não altere o contrato aprovado nem integre/publice automaticamente. Relate diff, verificações e pendências.`;
}
function interpolate(profile, vars) {
  return profile.args.map(x => x.replace(/\{(prompt|workspace|contract|rule)\}/g, (_,k) => vars[k]));
}
class AgentRunner {
  constructor(root, storage, output, onChange) { this.root=root; this.storage=storage; this.output=output; this.onChange=onChange; this.runs=new Map(); }
  list() { return [...this.runs.values()].map(({id,profile,rule,branch,status}) => ({id,profile,rule,branch,status})); }
  async start(profile, contract, rule, instruction) {
    validateProfile(profile);
    if (contract.status !== 'approved' || !rule.eligible || rule.waiting.length || rule.issues.length) throw new Error('Resolva a aprovação, decisões e dependências antes de iniciar esta regra.');
    const {stdout} = await exec('git', ['-C',this.root,'rev-parse','--show-toplevel']);
    if (await fs.promises.realpath(stdout.trim()) !== await fs.promises.realpath(this.root)) throw new Error('Abra a raiz Git do projeto no VS Code para isolar os agentes.');
    const {stdout: changes} = await exec('git', ['-C',this.root,'status','--porcelain','--untracked-files=no']);
    if (changes.trim()) throw new Error('Registre ou reverta alterações rastreadas antes de iniciar agentes; o worktree parte do último commit.');
    const id = crypto.randomUUID().slice(0,12), branch=`centaur/agent-${id}`, workspace=path.join(this.storage,'worktrees',id);
    await fs.promises.mkdir(path.dirname(workspace),{recursive:true});
    await exec('git',['-C',this.root,'worktree','add','-b',branch,workspace,'HEAD']);
    try {
      const rel = contract.path;
      const here = await fs.promises.readFile(path.join(this.root,rel));
      const there = await fs.promises.readFile(path.join(workspace,rel));
      if (!here.equals(there)) throw new Error('Contrato no checkout difere do último commit. Registre suas alterações antes de iniciar o agente.');
      const prompt=makePrompt(contract,rule,instruction);
      const args=interpolate(profile,{prompt,workspace,contract:contract.id,rule:rule.key});
      const child=spawn(profile.command,args,{cwd:workspace,shell:false,stdio:['ignore','pipe','pipe']});
      const run={id,profile:profile.label,rule:rule.key,branch,status:'em execução',child};this.runs.set(id,run);this.onChange();
      for(const channel of ['stdout','stderr'])child[channel].on('data',buffer=>this.output.append(buffer.toString().slice(0,20_000)));
      child.on('error',error=>{run.status='falhou: '+error.message;this.onChange();});
      child.on('close',code=>{if(run.status==='interrompendo')run.status='interrompido';else if(run.status==='em execução')run.status=code===0?'concluído':'falhou (código '+code+')';this.onChange();});
      this.output.appendLine(`\n[${id}] ${profile.label} / ${rule.key} / ${branch} / ${workspace}`);
      return run;
    } catch (error) {
      await exec('git',['-C',this.root,'worktree','remove','--force',workspace]).catch(()=>{});
      await exec('git',['-C',this.root,'branch','-D',branch]).catch(()=>{});
      throw error;
    }
  }
  stop(id){const run=this.runs.get(id);if(!run||run.status!=='em execução')throw new Error('Agente não está em execução.');run.status='interrompendo';run.child.kill('SIGINT');this.onChange();}
  dispose(){for(const run of this.runs.values())if(run.status==='em execução'||run.status==='interrompendo')run.child.kill('SIGINT');}
}
module.exports={AgentRunner,validateProfile,makePrompt,interpolate};
