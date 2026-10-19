import test from 'node:test';
import assert from 'node:assert/strict';
import {createSupportUI} from '../public/support-ui.js';

function fixture(){
  const requests=[];
  const responses={
    list_cases:{items:[{name:'CASE-1',student:'SV1',student_name:'Student One',status:'Open',priority:'High',target_date:'2026-10-20'}]},
    get_case:{case:{name:'CASE-1',student:'SV1',status:'Open',priority:'High',modified:'2026-10-19 12:00:00'},warnings:[],interventions:[]},
    get_support_dashboard:{summary:{active:1,closed:0,overdue:0},measurement:{return_rate:null,returned_cases:0,matured_cases:0,limited_to_latest:200},outcomes:[]},
    list_corrections:{items:[{name:'COR-1',student:'SV1',student_name:'Student One',original_status:'Absent',requested_status:'Present',status:'Pending',can_review:true,reason:'<script>bad</script>',evidence:'Evidence',modified:'2026-10-19 12:00:00'}]},
    list_my_attendance:{items:[{name:'ATT-1',status:'Absent',course_name:'PRF192',attendance_finalized:1}]},
    list_notifications:{items:[{name:'N1',subject:'Notice',read:0,document_type:'Student Warning',document_name:'W1'}],unread:1},
    get_data_quality:{unresolved:[{attendance:'ATT-OLD',student:'SV0'}]},
  };
  responses.get_correction=responses.list_corrections.items[0];responses.get_notification=responses.list_notifications.items[0];
  let modal='',closed=false,refreshed=false,warning=null;
  const state={page:0,ctx:{today:'2026-10-19'}};
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const ui=createSupportUI({request:async(method,data,verb)=>{requests.push({method,data,verb});return responses[method.split('.').at(-1)]||{};},
    esc,icon:()=>'',badge:(v,l)=>l||v,head:(t,s)=>t+s,stat:(l,v)=>l+v,empty:()=>'<empty>',date:v=>v||'—',num:v=>String(v||0),button:(l,a,c,i,attrs)=>`<button data-action="${a}" ${attrs||''}>${l}</button>`,state,
    roles:()=>({advisor:true}),openModal:html=>{modal=html;},closeButton:()=>'',toast(){},refresh:async()=>{refreshed=true;},showWarning:async id=>{warning=id;}});
  return {ui,state,requests,get modal(){return modal;},get refreshed(){return refreshed;},get warning(){return warning;}};
}

test('Support pages render scoped data and define an incomplete observation window',async()=>{
  const f=fixture();
  for(const page of ['cases','impact','corrections','my-attendance','notifications','quality']){
    const html=await f.ui.render(page);assert.ok(html.length>30,page);assert.ok(!html.includes('NaN'),page);
  }
  assert.match(await f.ui.render('impact'),/chưa chứng minh quan hệ nhân quả/);
  assert.ok(f.requests.every(r=>r.method.startsWith('student_crm.support.')));
});

test('Case form submits its own ID and optimistic version',async()=>{
  const f=fixture();await f.ui.action({dataset:{action:'support-case',id:'CASE-1'}});
  assert.match(f.modal,/support-case-form/);
  globalThis.document={querySelector:()=>({close(){}})};
  await f.ui.submit({id:'support-case-form'},{status:'Monitoring',priority:'High'});
  const saved=f.requests.find(r=>r.method.endsWith('.update_case'));
  assert.equal(saved.data.case,'CASE-1');assert.equal(saved.data.expected_modified,'2026-10-19 12:00:00');
  assert.equal(saved.verb,'POST');assert.equal(f.refreshed,true);
  delete globalThis.document;
});

test('Correction review escapes evidence and preserves request version',async()=>{
  const f=fixture();await f.ui.action({dataset:{action:'support-correction',id:'COR-1'}});
  assert.ok(!f.modal.includes('<script>'));assert.match(f.modal,/&lt;script&gt;/);
  assert.match(f.modal,/support-review-form/);
  globalThis.document={querySelector:()=>({close(){}})};
  await f.ui.submit({id:'support-review-form'},{decision:'Rejected',review_note:'Reviewed'});
  const saved=f.requests.find(r=>r.method.endsWith('.review_correction'));
  assert.equal(saved.data.correction,'COR-1');assert.equal(saved.data.expected_modified,'2026-10-19 12:00:00');
  delete globalThis.document;
});

test('Notification is marked read before opening its scoped warning detail',async()=>{
  const f=fixture();await f.ui.action({dataset:{action:'support-notification',id:'N1'}});
  assert.equal(f.requests.find(r=>r.method.endsWith('.mark_notification_read')).data.notification,'N1');
  assert.equal(f.warning,'W1');
});
