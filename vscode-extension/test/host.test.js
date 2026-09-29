const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const cp=require('node:child_process');
const Module=require('node:module');
const {hash}=require('../flow-store');

test('VS Code abre o painel, gera proposta por modelo e salva JSON validado',async()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'volante-host-'));
 cp.execFileSync('python3',[path.join(__dirname,'../../tests/support.py'),root]);
 let command,handler,panel;const sent=[];const context={globalStorageUri:{fsPath:path.join(root,'host')},subscriptions:[]};
 const model={name:'Modelo fictício',vendor:'teste',id:'local',async sendRequest(){const flow=JSON.parse(fs.readFileSync(path.join(root,'.centaur/use-cases/reservas.json')));return {text:[JSON.stringify({...flow,title:'Proposta por IA'})]};}};
 const vscode={Uri:{file:fsPath=>({fsPath,scheme:'file'})},ViewColumn:{One:1},LanguageModelChatMessage:{User:text=>({text})},lm:{selectChatModels:async()=>[model]},workspace:{isTrusted:true,workspaceFolders:[{name:'demo',uri:{fsPath:root,scheme:'file'}}],getConfiguration:()=>({get:(key,fallback)=>key==='python'?'python3':fallback}),onDidChangeConfiguration:()=>({dispose(){}})},commands:{registerCommand:(name,fn)=>{command=fn;return {dispose(){}};}},window:{showQuickPick:async items=>items[0],showErrorMessage:message=>{throw new Error(message);},createOutputChannel:()=>({append(){},appendLine(){},show(){},dispose(){}}),createWebviewPanel:()=>{panel={webview:{html:'',postMessage:async message=>{sent.push(message);},onDidReceiveMessage:fn=>{handler=fn;return {dispose(){}};}},onDidDispose:()=>({dispose(){}}),reveal(){},dispose(){}};return panel;}}};
 const disposable=()=>({dispose(){}});
 vscode.EventEmitter=class {event(){} fire(){} dispose(){}};
 vscode.window.createTreeView=disposable;
 vscode.workspace.createFileSystemWatcher=()=>({dispose(){},onDidChange:disposable,onDidCreate:disposable,onDidDelete:disposable});
 vscode.workspace.onDidChangeWorkspaceFolders=disposable;
 vscode.workspace.onDidGrantWorkspaceTrust=disposable;
 vscode.languages={registerInlineCompletionItemProvider:disposable};
 const original=Module._load;Module._load=function(request,...args){if(request==='vscode')return vscode;return original.call(this,request,...args);};
 let extension;try{extension=require('../extension');}finally{Module._load=original;}
 try{
  extension.activate(context);assert.equal(typeof command,'function');
  await command();
  assert.match(panel.webview.html,/Content-Security-Policy/);
  assert.match(panel.webview.html,/nonce=/);
  assert.doesNotMatch(panel.webview.html,/onclick=/);
  await handler({type:'ready'});
  await handler({type:'generateCase',contract:'reservas'});
  const generated=sent.find(x=>x.type==='generated');assert.equal(generated.case.title,'Proposta por IA');
  const existing=path.join(root,'.centaur/use-cases/reservas.json');
  await handler({type:'saveCase',case:generated.case,expectedHash:hash(fs.readFileSync(existing))});
  assert.equal(JSON.parse(fs.readFileSync(existing)).title,'Proposta por IA');
  assert(sent.some(x=>x.type==='project'&&x.data.use_cases.some(y=>y.title==='Proposta por IA')));
  await handler({type:'saveCase',case:generated.case,expectedHash:null});
  assert(sent.some(x=>x.type==='error'&&/mudou fora/.test(x.message)));
 }finally{extension.deactivate();for(const subscription of context.subscriptions)subscription.dispose();fs.rmSync(root,{recursive:true,force:true});}
});
