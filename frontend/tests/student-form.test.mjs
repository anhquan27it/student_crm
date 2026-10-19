import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

// Exercise the actual browser handlers with a directory payload (no form fields).
async function portal() {
  const source = await readFile(new URL('../public/app.js', import.meta.url), 'utf8');
  const handlers = {};
  const elements = new Map();
  const element = () => ({innerHTML:'',textContent:'',className:'',open:false,
    addEventListener(){},querySelector(){return null;},querySelectorAll(){return [];},contains(){return false;},
    showModal(){this.open=true;},close(){this.open=false;}});
  const context = vm.createContext({
    document:{querySelector(s){if(!elements.has(s))elements.set(s,element());return elements.get(s);},
      addEventListener(name, fn){handlers[name]=fn;}},
    window:{addEventListener(){}},location:{hash:'#/students',origin:'http://localhost'},URL,URLSearchParams,
    MutationObserver:class{observe(){}},
    FormData:class{constructor(form){return Object.entries(form.values);}},
    setTimeout:()=>0,clearTimeout(){},console,createSupportUI:()=>({}),createRoleUI:()=>({}),
  });
  vm.runInContext(source.replace(/^import .*;$/mg, '').replace(/boot\(\);\s*$/, ''), context);
  vm.runInContext(`
    state.ctx={roles:{admin:true}};
    state.route='students';state.data={items:[]};
    globalThis.calls=[];
    globalThis.studentSchema={doctype:'Student',editable:true,items:[],fields:[
      {name:'student_name',type:'Data',required:1},
      {name:'enabled',type:'Check'},
      {name:'score',type:'Float'}
    ]};
    globalThis.actualRequest=request;
    request=async (method,data,verb)=>{calls.push({method,data,verb});
      if(method==='get_catalog')return studentSchema;
      if(method==='save_record')return {name:'QA-STUDENT'};
      throw new Error('Unexpected request '+method);
    };
    globalThis.actualRoute=route;
    route=async()=>{globalThis.refreshed=true;};
  `, context);
  return {context,handlers,elements,run:code=>vm.runInContext(code,context)};
}

test('Add student opens a form directly without a hash navigation or directory schema',async()=>{
  const p=await portal();
  await p.run(`globalThis.trigger={dataset:{action:'add-student'},disabled:false};action(trigger)`);
  assert.equal(p.context.location.hash,'#/students');
  assert.equal(p.run('state.catalog'),'Course');
  assert.equal(p.run('state.recordForm.doctype'),'Student');
  assert.equal(p.elements.get('#modal').open,true);
  assert.match(p.elements.get('#modal-content').innerHTML,/name="student_name"/);
  assert.equal(p.run('trigger.disabled'),false);
});

test('Student save keeps its own schema and doctype when page state changes',async()=>{
  const p=await portal();
  await p.run(`action({dataset:{action:'add-student'}})`);
  p.run(`state.catalog='Course';state.data={items:[]};`);
  const submit={disabled:false};
  await p.handlers.submit({preventDefault(){},target:{id:'record-form',
    values:{student_name:'Test Student',score:'2.5'},
    elements:{enabled:{checked:true}},querySelector(){return submit;}}});
  const saved=p.context.calls.find(c=>c.method==='save_record');
  assert.equal(saved.data.doctype,'Student');
  assert.equal(saved.data.name,null);
  assert.equal(saved.data.data.student_name,'Test Student');
  assert.equal(saved.data.data.enabled,1);
  assert.equal(saved.data.data.score,2.5);
  assert.equal(p.context.refreshed,true);
  assert.equal(p.elements.get('#modal').open,false);
  assert.equal(submit.disabled,false);
});

test('Failed student schema request restores the button and reports the error',async()=>{
  const p=await portal();
  p.run(`request=async()=>{throw new Error('Cannot load student form');};`);
  await p.run(`globalThis.trigger={dataset:{action:'add-student'},disabled:false};action(trigger)`);
  assert.equal(p.run('trigger.disabled'),false);
  assert.equal(p.elements.get('#modal').open,false);
  assert.equal(p.elements.get('#toast').textContent,'Cannot load student form');
});

test('Cancel controls are never implicit form submitters',async()=>{
  const p=await portal();
  assert.match(p.run("button('Hủy','close-modal')"),/type="button"/);
  assert.match(p.run('closeButton()'),/type="button"/);
});

test('Dirty modal remains open when discard is cancelled and while saving',async()=>{
  const p=await portal();
  p.run('modal.showModal();state.modalDirty=true;globalThis.confirm=()=>false;');
  assert.equal(p.run('closeModal()'),false);
  assert.equal(p.elements.get('#modal').open,true);
  p.run('globalThis.confirm=()=>true;state.modalBusy=1;');
  assert.equal(p.run('closeModal()'),false);
  p.run('state.modalBusy=0;');
  assert.equal(p.run('closeModal()'),true);
  assert.equal(p.elements.get('#modal').open,false);
});

test('Record edit sends the original optimistic version',async()=>{
  const p=await portal();
  await p.run(`recordModal(0,{...studentSchema,items:[{name:'QA-STUDENT',modified:'2026-10-19 10:00:00'}]})`);
  await p.handlers.submit({preventDefault(){},target:{id:'record-form',values:{student_name:'Edited',score:'2'},elements:{enabled:{checked:true}},querySelector(){return null;}}});
  assert.equal(p.context.calls.find(c=>c.method==='save_record').data.expected_modified,'2026-10-19 10:00:00');
});

test('Duplicate submission is ignored while the first save is pending',async()=>{
  const p=await portal();await p.run(`action({dataset:{action:'add-student'}})`);
  p.run(`globalThis.saved=0;globalThis.release=null;request=async()=>{saved++;await new Promise(r=>release=r);return {name:'QA'};};`);
  const form={id:'record-form',values:{student_name:'QA',score:'1'},elements:{enabled:{checked:false}},querySelector(){return null;}};
  const first=p.handlers.submit({preventDefault(){},target:form});
  await p.handlers.submit({preventDefault(){},target:form});
  assert.equal(p.run('saved'),1);p.run('release()');await first;
});

test('Expired login clears all user-specific cached state',async()=>{
  const p=await portal();
  p.run(`state.dirty=true;state.roster={students:[{student:'old'}]};state.term='OLD';state.search='private';login('Expired');`);
  assert.equal(p.run('state.ctx'),null);assert.equal(p.run('state.roster'),null);
  assert.equal(p.run('state.term'),'');assert.equal(p.run('state.search'),'');assert.equal(p.run('state.dirty'),false);
});

test('Valid-session permission denial does not log the user out',async()=>{
  const p=await portal();
  p.run(`state.ctx={user:'QA',roles:{admin:false}};globalThis.fetch=async url=>String(url).includes('get_context')?{status:200}:{ok:false,status:403,json:async()=>({exc_type:'PermissionError'})};`);
  await assert.rejects(p.run("actualRequest('get_catalog')"),e=>e.type==='PermissionError');
  assert.equal(p.run('state.ctx.user'),'QA');
});

test('Expired session returning 403 shows login and clears private state',async()=>{
  const p=await portal();
  p.run(`state.ctx={user:'QA',roles:{}};state.roster={students:[]};globalThis.fetch=async()=>({ok:false,status:403,json:async()=>({exc_type:'PermissionError'})});`);
  await assert.rejects(p.run("actualRequest('list_sessions')"),e=>e.type==='SessionExpired'&&e.status===401);
  assert.equal(p.run('state.ctx'),null);assert.equal(p.run('state.roster'),null);
  assert.match(p.elements.get('#app').innerHTML,/Phiên đăng nhập đã hết hạn/);
});

test('Attendance save expiry does not try to write into a removed roster',async()=>{
  const p=await portal();
  p.run(`state.roster={session:{name:'QA',modified:'now'},students:[{student:'QA',status:'Present'}]};
    const select=document.querySelector;document.querySelector=s=>s==='#roster-error'?null:select(s);
    request=async()=>{throw Object.assign(new Error('Expired'),{type:'SessionExpired'});};`);
  await p.run(`action({dataset:{action:'save-roster'}})`);
  assert.equal(p.run('state.rosterSaving'),false);
  assert.equal(p.elements.get('#toast')?.textContent||'','');
});

test('Navigation is blocked while an attendance save is pending',async()=>{
  const p=await portal();
  p.run(`state.route='roster';state.lastHash='#/roster/QA';state.rosterSaving=true;location.hash='#/sessions';
    globalThis.history={replaceState:(a,b,hash)=>{location.hash=hash;}};`);
  await p.run('actualRoute()');
  assert.equal(p.context.location.hash,'#/roster/QA');
  assert.equal(p.run('state.route'),'roster');
  assert.match(p.elements.get('#toast').textContent,/Đang lưu/);
});
