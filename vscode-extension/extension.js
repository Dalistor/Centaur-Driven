'use strict';
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {execFile} = require('node:child_process');
const {promisify} = require('node:util');
const {validate,saveFlow} = require('./flow-store');
const {AgentRunner,validateProfile} = require('./agent-runner');
const {registerEditor} = require('./editor-context');
const {registerCompletion} = require('./completion');
const exec = promisify(execFile);

let panel, root, data, runner, output, pending;
function errorText(e) { return typeof e?.message === 'string' ? e.message.slice(0,350) : 'Operação indisponível.'; }
function send(message) { panel?.webview.postMessage(message); }
function profiles() {
  const items=vscode.workspace.getConfiguration('centaurVolante',vscode.Uri.file(root)).get('agentProfiles',[]);
  if(!Array.isArray(items))return [];
  const valid=[];const ids=new Set();
  for(const p of items){validateProfile(p);if(ids.has(p.id))throw new Error('IDs de agentes repetidos.');ids.add(p.id);valid.push(p);}
  return valid;
}
function profileState(){send({type:'profiles',profiles:profiles().map(({id,label})=>({id,label})),running:runner?.list()||[]});}
function withCsp(html,webview) {
  const nonce=crypto.randomBytes(16).toString('base64');
  const csp=`default-src 'none'; script-src 'nonce-${nonce}'; style-src 'nonce-${nonce}'; img-src data:; font-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'`;
  return html.replace('<style>',`<meta http-equiv="Content-Security-Policy" content="${csp}"><style nonce="${nonce}">`).replace(/<script(\s|>)/g,`<script nonce="${nonce}"$1`);
}
async function snapshot(updateHtml=true) {
  const python=vscode.workspace.getConfiguration('centaurVolante',vscode.Uri.file(root)).get('python','python3');
  const engine=path.join(__dirname,'dist/engine/render-volante.py');
  await exec(python,[engine,root],{cwd:root,timeout:20_000,maxBuffer:2_000_000});
  const html=await fs.promises.readFile(path.join(root,'.centaur/volante.html'),'utf8');
  const match=html.match(/<script id="volante-data" type="application\/json">([^<]*)<\/script>/);
  if(!match)throw new Error('Snapshot sem dados do Volante.');
  data=JSON.parse(match[1]);
  if(updateHtml)panel.webview.html=withCsp(html,panel.webview);
  else send({type:'project',data});
}
async function chooseRoot(){
  const folders=(vscode.workspace.workspaceFolders||[]).filter(f=>f.uri.scheme==='file');
  if(!folders.length)throw new Error('Abra a pasta local do projeto Centaur.');
  const picked=folders.length===1?folders[0]:(await vscode.window.showQuickPick(folders.map(f=>({label:f.name,description:f.uri.fsPath,value:f})),{placeHolder:'Selecione o projeto Centaur'}))?.value;
  if(!picked)return null;
  const file=path.join(picked.uri.fsPath,'.centaur/workspace.json');
  if(!(await fs.promises.stat(file).catch(()=>null))?.isFile())throw new Error('Esta pasta não contém .centaur/workspace.json.');
  return picked.uri.fsPath;
}
function requireTrust(){if(!vscode.workspace.isTrusted)throw new Error('Confie na pasta do VS Code para salvar fluxos ou iniciar agentes.');}
async function generateFlow(contractId){
  requireTrust();
  const contract=data.contracts.find(c=>c.id===contractId);if(!contract)throw new Error('Contrato não encontrado.');
  const models=await vscode.lm.selectChatModels({});
  if(!models.length)throw new Error('Nenhum modelo de linguagem disponível no VS Code. Instale ou conecte um provedor.');
  const pick=await vscode.window.showQuickPick(models.map(model=>({label:model.name,description:`${model.vendor} · ${model.id}`,model})),{placeHolder:'Escolha o modelo para propor este fluxo'});
  if(!pick){send({type:'error',message:'Geração cancelada.'});return;}
  const model=pick.model;
  const prompt=`Responda somente um objeto JSON, sem markdown. Proponha um fluxograma de caso de uso em português para este contrato. Não invente uma aprovação nem mude requisitos. O objeto deve conter exatamente schema:1, contract:${JSON.stringify(contract.id)}, version:${contract.version}, title (até 500 caracteres), summary (até 500), nodes (1 a 32 objetos com id alfanumérico iniciado em letra, kind start/action/decision/end, label até 120, detail até 500), edges (0 a 64 objetos com from,to,label até 80). Inclua pelo menos um start e ramificações com rótulos quando houver decisões. IDs únicos; arestas referem-se a IDs existentes e não apontam a si mesmas.\nContrato: ${JSON.stringify({id:contract.id,version:contract.version,title:contract.title,intent:contract.intent,boundaries:contract.boundaries,autonomy:contract.autonomy,decisions:contract.decisions,rules:contract.rules.map(r=>({id:r.id,description:r.description,acceptance:r.acceptance,depends_on:r.depends_on}))})}`;
  const response=await model.sendRequest([vscode.LanguageModelChatMessage.User(prompt)],{});
  let text='';for await(const chunk of response.text){text+=chunk;if(text.length>60_000)throw new Error('Resposta do modelo excedeu o limite do fluxograma.');}
  const start=text.indexOf('{'),end=text.lastIndexOf('}');if(start<0||end<=start)throw new Error('O modelo não retornou um JSON. Tente novamente.');
  let value;try{value=JSON.parse(text.slice(start,end+1));}catch{throw new Error('O JSON proposto pelo modelo é inválido. Tente novamente.');}
  send({type:'generated',case:validate(value,contract)});
}
async function handle(message){
  if(!message||typeof message.type!=='string')return;
  try{
    if(message.type==='ready'){profileState();if(pending){send(pending);pending=null;}return;}
    if(message.type==='saveCase'){
      requireTrust();
      const contract=data.contracts.find(c=>c.id===message.case?.contract);if(!contract)throw new Error('Contrato não encontrado.');
      await saveFlow(root,message.case,contract,message.expectedHash??null);
      await snapshot(false);
      send({type:'saved',contract:contract.id});return;
    }
    if(message.type==='generateCase'){await generateFlow(message.contract);return;}
    if(message.type==='openSettings'){await vscode.commands.executeCommand('workbench.action.openSettings','centaurVolante.agentProfiles');return;}
    if(message.type==='startAgents'){
      requireTrust();const profile=profiles().find(p=>p.id===message.profile);
      const keys=message.rules;
      if(!profile||!Array.isArray(keys)||keys.length<1||keys.length>4||new Set(keys).size!==keys.length)throw new Error('Selecione de uma a quatro regras diferentes e um perfil válido.');
      const tasks=keys.map(key=>{const rule=data.contracts.flatMap(c=>c.rules).find(r=>r.key===key);if(!rule||!rule.eligible||rule.waiting.length||rule.issues.length)throw new Error(`Regra ${key} não está liberada.`);return {rule,contract:data.contracts.find(c=>c.id===rule.contract)};});
      let started=0;
      try{for(const task of tasks){await runner.start(profile,task.contract,task.rule,message.instruction);started++;profileState();}}
      catch(e){throw new Error(`${started} agente(s) iniciados; próxima execução falhou: ${errorText(e)}`);}
      output.show(true);return;
    }
    if(message.type==='stopAgent'){runner.stop(message.id);profileState();return;}
  }catch(e){send({type:'error',message:errorText(e)});output?.appendLine(errorText(e));}
}
function activate(context){
  output=vscode.window.createOutputChannel('Centaur Volante');context.subscriptions.push(output);
  const projects=registerEditor(vscode,context,output);
  registerCompletion(vscode,context,projects,output);
  context.subscriptions.push(vscode.commands.registerCommand('centaurVolante.open',async()=>{
    try{
      requireTrust();const target=await chooseRoot();if(!target)return;
      if(root && root!==target){
        if(runner?.list().some(run=>['em execução','interrompendo'].includes(run.status)))throw new Error('Há agentes ativos no projeto anterior. Reabra seu painel para interrompê-los antes de trocar de projeto.');
        panel?.dispose();panel=null;runner?.dispose();runner=null;
      }
      root=target;
      if(!panel){
        panel=vscode.window.createWebviewPanel('centaurVolante','Volante · '+path.basename(root),vscode.ViewColumn.One,{enableScripts:true,retainContextWhenHidden:true,localResourceRoots:[]});
        panel.webview.onDidReceiveMessage(handle,null,context.subscriptions);
        panel.onDidDispose(()=>{panel=null;},null,context.subscriptions);
        runner=runner||new AgentRunner(root,path.join(root,'.centaur'),output,()=>{try{profileState();}catch(e){output.appendLine(errorText(e));}});
      }else panel.reveal();
      await snapshot();
    }catch(e){vscode.window.showErrorMessage('Volante: '+errorText(e));}
  }));
  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(event=>{if(panel&&event.affectsConfiguration('centaurVolante.agentProfiles'))try{profileState();}catch(e){send({type:'error',message:errorText(e)});}}));
  context.subscriptions.push({dispose(){runner?.dispose();}});
}
function deactivate(){runner?.dispose();}
module.exports={activate,deactivate};
