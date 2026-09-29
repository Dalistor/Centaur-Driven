const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const {safeFile,projectNodes,relatedContext} = require('../context-tree');
const {registerCompletion} = require('../completion');

test('source navigation rejects traversal and symlink escapes', async () => {
  const base = await fs.mkdtemp(path.join(os.tmpdir(),'centaur-path-'));
  try {
    const root=path.join(base,'project');await fs.mkdir(root);
    await fs.writeFile(path.join(root,'code.js'),'ok');await fs.writeFile(path.join(base,'secret'),'secret');
    await fs.symlink(path.join(base,'secret'),path.join(root,'link'));
    assert.equal(await safeFile(root,'code.js'),path.join(root,'code.js'));
    await assert.rejects(safeFile(root,'../secret'),/fora/);
    await assert.rejects(safeFile(root,'link'),/fora/);
    await assert.rejects(safeFile(root,path.join(root,'code.js')),/inválida/);
  } finally {await fs.rm(base,{recursive:true,force:true});}
});

test('tree links source/test/evidence and exposes stale verification', () => {
  const data={contracts:[{id:'booking',version:2,title:'Booking',rules:[{id:'R1',description:'Reserve',verification:'desatualizada',sources:[{path:'test.js',role:'Teste',start:5}],evidence:[{path:'.centaur/evidence/test.json',verification:'desatualizada',summary:'Test'}]}]}]};
  const nodes=projectNodes('/project',data);
  assert.equal(nodes[0].children[0].source.path,'.centaur/contracts/booking/v002.json');
  assert.equal(nodes[0].children[1].description,'RF · desatualizada');
  assert.equal(nodes[0].children[1].children[1].source.start,5);
  assert.equal(relatedContext(data,'test.js')[0].rule,'R1');
  assert.deepEqual(relatedContext(data,'other.js'),[]);
});

test('autocomplete is opt-in, excludes secrets and cancels outdated responses', async () => {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'centaur-completion-'));
  const commands={},subscriptions=[];let calls=0,document,cancelRequest,mode='stale';
  const model={name:'test',vendor:'test',id:'test',async sendRequest(){calls++;if(mode==='stale')document.version++;else cancelRequest();return {text:['wrong']};}};
  const vscode={commands:{registerCommand:(id,fn)=>{commands[id]=fn;return {dispose(){}};}},workspace:{isTrusted:true,getWorkspaceFolder:()=>({uri:{fsPath:root}})},window:{showQuickPick:async values=>values[0]},lm:{selectChatModels:async()=>[model]},languages:{registerInlineCompletionItemProvider:()=>({dispose(){}})},LanguageModelChatMessage:{User:value=>value},CancellationTokenSource:class{token={isCancellationRequested:false};cancel(){this.token.isCancellationRequested=true;}dispose(){}}};
  const provider=registerCompletion(vscode,{subscriptions},new Map([[root,{contracts:[]}]]),{appendLine(){}});
  const token={isCancellationRequested:false,onCancellationRequested:fn=>{cancelRequest=fn;return {dispose(){}};}};
  document={uri:{scheme:'file',fsPath:path.join(root,'code.js')},version:1,getText:()=> 'code',offsetAt:()=>4,languageId:'javascript'};
  try {
    await fs.writeFile(document.uri.fsPath,'code');
    assert.deepEqual(await provider.provideInlineCompletionItems(document,{},null,token),[]);assert.equal(calls,0);
    await commands['centaurVolante.enableCompletion']();
    document.uri.fsPath=path.join(root,'.env');
    assert.deepEqual(await provider.provideInlineCompletionItems(document,{},null,token),[]);assert.equal(calls,0);
    await fs.writeFile(path.join(root,'.env'),'secret');
    await fs.symlink(path.join(root,'.env'),path.join(root,'alias.js'));
    document.uri.fsPath=path.join(root,'alias.js');
    assert.deepEqual(await provider.provideInlineCompletionItems(document,{},null,token),[]);assert.equal(calls,0);
    document.uri.fsPath=path.join(root,'code.js');
    assert.deepEqual(await provider.provideInlineCompletionItems(document,{},null,token),[]);assert.equal(calls,1);
    mode='cancel';
    assert.deepEqual(await provider.provideInlineCompletionItems(document,{},null,token),[]);assert.equal(calls,2);
    commands['centaurVolante.disableCompletion']();
    assert.deepEqual(await provider.provideInlineCompletionItems(document,{},null,token),[]);assert.equal(calls,2);
  } finally {subscriptions.forEach(s=>s.dispose());await fs.rm(root,{recursive:true,force:true});}
});

test('native tree reads real fixture without HTML and refreshes on linked source changes', async () => {
  const {registerEditor} = require('../editor-context');
  const cp = require('node:child_process');
  const root = await fs.mkdtemp(path.join(os.tmpdir(),'centaur-tree-'));
  cp.execFileSync('python3',[path.join(__dirname,'../../tests/support.py'),root]);
  await fs.rm(path.join(root,'.centaur/volante.html'),{force:true});
  const subscriptions=[],commands={};let provider,change,notified;
  const folder={name:'fixture',uri:{scheme:'file',fsPath:root}};
  const disposable=()=>({dispose(){}});
  const vscode={
    EventEmitter:class {event(){} fire(){notified?.();} dispose(){}},
    window:{createTreeView:(_id,options)=>{provider=options.treeDataProvider;return disposable();}},
    workspace:{isTrusted:true,workspaceFolders:[folder],getWorkspaceFolder:()=>folder,getConfiguration:()=>({get:(_key,fallback)=>fallback}),createFileSystemWatcher:()=>({dispose(){},onDidChange:fn=>{change=fn;return disposable();},onDidCreate:disposable,onDidDelete:disposable}),onDidChangeWorkspaceFolders:disposable,onDidGrantWorkspaceTrust:disposable,onDidChangeConfiguration:disposable},
    commands:{registerCommand:(id,fn)=>{commands[id]=fn;return disposable();}}
  };
  try {
    let ready=new Promise(resolve=>{notified=resolve;});
    const projects=registerEditor(vscode,{subscriptions},{appendLine:message=>assert.fail(message)});
    await ready;
    assert.equal(projects.size,1);
    assert.equal(provider.getChildren()[0].label,'fixture');
    await assert.rejects(fs.stat(path.join(root,'.centaur/volante.html')),{code:'ENOENT'});
    const source=projects.get(root).contracts.flatMap(c=>c.rules).flatMap(r=>r.sources)[0];
    ready=new Promise(resolve=>{notified=resolve;});
    change({fsPath:path.join(root,source.path)});
    await ready;
    assert.equal(projects.size,1);
  } finally {subscriptions.forEach(s=>s.dispose());await fs.rm(root,{recursive:true,force:true});}
});

test('conceptual specification is navigable and bounded context excludes evidence payloads', () => {
  const specification={actors:['Customer'],exclusions:['Payments'],use_cases:[{id:'UC1',title:'Reserve',actor:'Customer',main_flow:['Choose','Confirm'],rules:['R1']}],data_model:{entities:[{name:'Reservation',attributes:['id'],invariants:['Unique']}],relationships:[{from:'Customer',to:'Reservation',cardinality:'1:N',invariants:[]}]}};
  const data={contracts:[{id:'book',version:1,intent:'Booking',specification,rules:[{id:'R1',kind:'non_functional',verification:'aprovada',sources:[{path:'code.js'}],evidence:[{summary:'private evidence detail'}]}]}]};
  const contract=projectNodes('/project',data)[0];
  assert.match(contract.children[1].description,/RNF/);
  const concept=contract.children.find(node=>node.label==='Conceito e especificação');
  assert.equal(concept.children.find(node=>node.label==='UC1: Reserve').children[1].children[0].label,'Choose');
  assert.match(concept.children.find(node=>node.label==='Modelo de dados').children[1].label,/1:N/);
  const related=relatedContext(data,'code.js');
  assert.equal(related[0].specification,specification);
  assert.doesNotMatch(JSON.stringify(related),/private evidence/);
});
