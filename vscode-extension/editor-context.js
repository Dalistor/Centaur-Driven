'use strict';
const path = require('node:path');
const {promisify} = require('node:util');
const exec = promisify(require('node:child_process').execFile);
const {safeFile,projectNodes} = require('./context-tree');

function registerEditor(vscode, context, output) {
  const changed = new vscode.EventEmitter();
  const projects = new Map();
  let nodes = [], timer, loading = false, requested = false, disposed = false;
  const tree = vscode.window.createTreeView('centaurContext', {treeDataProvider:{
    onDidChangeTreeData:changed.event,
    getChildren:item => item ? item.children : nodes,
    getTreeItem:item => {
      const view = new vscode.TreeItem(item.label, item.children.length ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
      view.description = item.description;
      if(item.source) view.command = {command:'centaurVolante.openSource',title:'Abrir código',arguments:[item]};
      return view;
    }
  }});
  async function refresh() {
    if(disposed) return;
    if(loading) {requested = true;return;}
    loading = true;
    try {
      do {
        requested = false;
        projects.clear(); nodes = [];
        if(!vscode.workspace.isTrusted) {nodes.push({label:'Confie no projeto para carregar o contexto.',children:[]});break;}
        for(const folder of vscode.workspace.workspaceFolders || []) {
          if(folder.uri.scheme !== 'file') continue;
          const root = folder.uri.fsPath;
          try {
            await safeFile(root,'.centaur/workspace.json');
          } catch {continue;}
          try {
            const python = vscode.workspace.getConfiguration('centaurVolante',folder.uri).get('python','python3');
            const result = await exec(python,[path.join(__dirname,'dist/engine/export-context.py'),root],{cwd:root,timeout:20000,maxBuffer:4_000_000});
            const data = JSON.parse(result.stdout);
            projects.set(root,data);
            nodes.push({label:folder.name,children:projectNodes(root,data)});
          } catch(error) {nodes.push({label:`${folder.name}: contexto indisponível`,description:error.message.slice(0,200),children:[]});output.appendLine(error.message);}
        }
        if(!nodes.length) nodes.push({label:'Abra um projeto com .centaur/workspace.json',children:[]});
      } while(requested && !disposed);
    } finally {loading = false;if(!disposed) changed.fire();}
  }
  async function openSource(item) {
    try {
      const filename = await safeFile(item.root,item.source.path);
      const document = await vscode.workspace.openTextDocument(vscode.Uri.file(filename));
      const line = Math.max(0,Math.min(document.lineCount-1,(item.source.start || 1)-1));
      const editor = await vscode.window.showTextDocument(document);
      editor.selection = new vscode.Selection(line,0,line,0);
      editor.revealRange(new vscode.Range(line,0,line,0));
    } catch(error) {vscode.window.showErrorMessage('Centaur: ' + error.message);}
  }
  const schedule = () => {clearTimeout(timer);timer = setTimeout(refresh,400);};
  const watcher = vscode.workspace.createFileSystemWatcher('**/*');
  const onFile = uri => {
    const folder = vscode.workspace.getWorkspaceFolder(uri);
    if(!folder) return;
    const relative = path.relative(folder.uri.fsPath,uri.fsPath).split(path.sep).join('/');
    if(/^\.centaur\/(?:workspace\.json$|contracts\/|state\/|evidence\/|use-cases\/|system\/)/.test(relative) || projects.get(folder.uri.fsPath)?.contracts.some(c => c.rules.some(r => r.sources.some(s => s.path === relative) || r.evidence.some(e => Object.hasOwn(e.files || {}, relative))))) schedule();
  };
  context.subscriptions.push(tree,changed,watcher,watcher.onDidChange(onFile),watcher.onDidCreate(onFile),watcher.onDidDelete(onFile),
    vscode.workspace.onDidChangeWorkspaceFolders(schedule),vscode.workspace.onDidGrantWorkspaceTrust(schedule),
    vscode.workspace.onDidChangeConfiguration(e => {if(e.affectsConfiguration('centaurVolante.python')) schedule();}),
    vscode.commands.registerCommand('centaurVolante.refresh',refresh),
    vscode.commands.registerCommand('centaurVolante.openSource',openSource),
    vscode.commands.registerCommand('centaurVolante.tests',() => vscode.commands.executeCommand('workbench.view.testing')),
    vscode.commands.registerCommand('centaurVolante.debug',() => vscode.commands.executeCommand('workbench.view.debug')),
    vscode.commands.registerCommand('centaurVolante.diff',() => vscode.commands.executeCommand('workbench.view.scm')),
    {dispose(){disposed=true;clearTimeout(timer);projects.clear();}});
  refresh();
  return projects;
}
module.exports = {registerEditor};
