const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const cp=require('node:child_process');
const {validate,saveFlow,hash}=require('../flow-store');
const {AgentRunner,validateProfile,interpolate}=require('../agent-runner');
const contract={id:'reservas',version:1,status:'approved',path:'.centaur/contracts/reservas/v001.json',boundaries:['Preservar autenticação'],autonomy:['Implementar agenda']};
const rule={key:'reservas/RES-01',description:'Consultar horários',acceptance:['Somente horários livres'],eligible:true,waiting:[],issues:[]};
function flow(){return {schema:1,contract:'reservas',version:1,title:'Reservar consulta',summary:'Fluxo de reserva',nodes:[{id:'inicio',kind:'start',label:'Paciente inicia',detail:''},{id:'fim',kind:'end',label:'Reserva feita',detail:''}],edges:[{from:'inicio',to:'fim',label:''}]};}
function temp(){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'volante-extension-'));return {dir,dispose:()=>fs.rmSync(dir,{recursive:true,force:true})};}
test('fluxo valida IDs, referências e vínculo à versão do contrato',()=>{
  assert.equal(validate(flow(),contract).nodes.length,2);
  assert.throws(()=>validate({...flow(),version:2},contract),/versão/);
  assert.throws(()=>validate({...flow(),edges:[{from:'inicio',to:'outro'}]},contract),/inexistente/);
  assert.throws(()=>validate({...flow(),nodes:[{id:'x',kind:'action',label:'Sem início'}]},contract),/início/);
});
test('salvar JSON é atômico, exige hash e bloqueia symlink',async()=>{
  const t=temp();try{
    await fs.promises.mkdir(path.join(t.dir,'.centaur'),{recursive:true});
    const saved=await saveFlow(t.dir,flow(),contract,null);
    const bytes=await fs.promises.readFile(saved.path);
    assert.equal(saved.hash,hash(bytes));
    await assert.rejects(saveFlow(t.dir,flow(),contract,null),/mudou fora/);
    await saveFlow(t.dir,{...flow(),summary:'Revisado'},contract,saved.hash);
    const outside=path.join(t.dir,'outside.json');fs.writeFileSync(outside,'segredo');
    await fs.promises.rm(saved.path);await fs.promises.symlink(outside,saved.path);
    await assert.rejects(saveFlow(t.dir,flow(),contract,null),/link simbólico/);
    assert.equal(fs.readFileSync(outside,'utf8'),'segredo');
  }finally{t.dispose();}
});
test('agentes criam worktrees diferentes, sem shell, e preservam branches para revisão',async()=>{
  const t=temp();const root=path.join(t.dir,'repo'),storage=path.join(t.dir,'storage');fs.mkdirSync(root,{recursive:true});
  const git=(...args)=>cp.execFileSync('git',['-C',root,...args],{stdio:'pipe'}).toString().trim();
  try{
    git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.local');
    const file=path.join(root,contract.path);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(contract));git('add','.');git('commit','-qm','Initial');
    const log={append(){},appendLine(){}};const runner=new AgentRunner(root,storage,log,()=>{});
    const profile={id:'node',label:'Node test',command:process.execPath,args:['-e','process.stdout.write(process.cwd())','{prompt}']};
    validateProfile(profile);assert.equal(interpolate(profile,{prompt:'a; touch /tmp/no',workspace:root,contract:'x',rule:'y'})[2],'a; touch /tmp/no');
    const [a,b]=await Promise.all([runner.start(profile,contract,rule,''),runner.start(profile,contract,rule,'')]);
    assert.notEqual(a.branch,b.branch);assert.equal(runner.list().length,2);
    assert(fs.existsSync(path.join(storage,'worktrees',a.id,contract.path)));
    assert(fs.existsSync(path.join(storage,'worktrees',b.id,contract.path)));
    await new Promise(resolve=>setTimeout(resolve,100));
    for(const run of [a,b]){assert.notEqual(run.status,'em execução');git('worktree','remove','--force',path.join(storage,'worktrees',run.id));git('branch','-D',run.branch);}
    fs.writeFileSync(file,JSON.stringify({...contract,status:'draft'}));
    await assert.rejects(runner.start(profile,contract,rule,''),/alterações rastreadas/);
    runner.dispose();
  }finally{t.dispose();}
});
