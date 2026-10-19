// For the portable 100-student seed. Config {site,password,upstream?} via stdin.
import assert from 'node:assert/strict';
import {createInterface} from 'node:readline';
const input=createInterface({input:process.stdin,terminal:false});
const config=JSON.parse(await new Promise(r=>input.once('line',r)));input.close();process.stdin.pause();
if(config.site)process.env.FRAPPE_SITE=config.site;
if(config.upstream)process.env.FRAPPE_URL=config.upstream;
const {server}=await import('../server.mjs');
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;
let checks=0;const ok=(v,l)=>{assert.ok(v,l);checks++;console.log('PASS '+l);};
function client(){const cookies=new Map();let csrf='';return async(method,data={},verb='GET',useCsrf=true)=>{
 const url=new URL('/api/method/'+method,base);if(verb==='GET')for(const[k,v]of Object.entries(data))url.searchParams.set(k,v);
 const r=await fetch(url,{method:verb,headers:{cookie:[...cookies].map(([k,v])=>k+'='+v).join('; '),'content-type':'application/json',...(verb==='POST'&&csrf&&useCsrf?{'x-frappe-csrf-token':csrf}:{})},body:verb==='POST'?JSON.stringify(data):undefined});
 for(const cookie of r.headers.getSetCookie()){const pair=cookie.split(';')[0],n=pair.indexOf('=');cookies.set(pair.slice(0,n),pair.slice(n+1));}
 const body=await r.json();if(method==='student_crm.portal.get_context'&&r.ok)csrf=body.message.csrf_token;return {status:r.status,data:body.message,body};
};}
const clients=[];
async function login(user){const c=client();clients.push(c);ok((await c('login',{usr:user,pwd:config.password},'POST')).status===200,'Login '+user);await c('student_crm.portal.get_context');return c;}
try{
 const p='student_crm.portal.',s='student_crm.support.',a='student_crm.api.',e='student_crm.experience.';
 ok((await fetch(base)).status===200,'Frontend serves HTML');
 ok((await fetch(base+'/api/resource/User')).status===404,'Raw resource routes blocked');
 ok((await client()(p+'get_context')).status===403,'Guest denied');
 const advisor=await login('demo.crm.faculty01@example.com');
 let r=await advisor(p+'list_students');ok(r.data.total_count===34,'Advisor has 34 synthetic advisees');
 ok((await advisor(p+'get_student_detail',{student:'DEMO-20261019-SV002'})).status===403,'Cross-advisor profile denied');
 ok((await advisor(p+'get_catalog')).status===403,'Advisor catalog denied');
 ok((await advisor(e+'get_workbench')).data.role==='advisor','Advisor workbench');
 ok((await advisor(s+'list_cases')).data.items.length>0,'Linked support cases');
 ok((await advisor(s+'list_notifications')).data.items.length>0,'In-app notifications');
 ok((await advisor(s+'get_support_dashboard')).status===200,'Support outcome report');
 const teacher=await login('demo.crm.faculty04@example.com');
 ok((await teacher(p+'list_offerings')).data.items.length===3,'Teacher sees three assigned classes');
 r=await teacher(a+'get_session_roster',{class_session:'DEMO-20261019-CEA201-S01'});
 ok(r.data.count===34,'Roster contains all 34 enrolled students');
 const data={class_session:r.data.session.name,expected_modified:r.data.session.modified,attendance_data:r.data.students.map(x=>({student:x.student,status:x.status,late_minutes:x.late_minutes||0}))};
 ok((await teacher(a+'submit_bulk_attendance',data,'POST',false)).body.exc_type==='CSRFTokenError','Missing CSRF rejected');
 ok((await teacher(a+'submit_bulk_attendance',data,'POST')).data.idempotent===true,'Finalized roster replay is idempotent');
 ok((await teacher(a+'get_session_roster',{class_session:'DEMO-20261019-CSI106-S01'})).status===403,'Other instructor roster denied');
 const student=await login('demo.crm.student001@example.com');
 r=await student(p+'get_overview');ok(r.data.enrollments.length===5&&r.data.profile.name==='DEMO-20261019-SV001','Own five enrollments');
 ok(r.data.interventions.length===0,'Advisor private notes not exposed');
 ok((await student(s+'list_my_attendance')).data.items.length===40,'Student has forty attendance records');
 ok((await student(p+'get_student_detail',{student:'DEMO-20261019-SV002'})).status===403,'Other student profile denied');
 ok((await student(a+'get_advisor_dashboard')).status===403,'Student advisor dashboard denied');
 const boundary=await login('demo.crm.student010@example.com');
 r=await boundary(p+'get_overview');ok(r.data.enrollments.some(x=>x.absent_count===4&&x.attendance_standing==='Critical'),'Exactly 4/20 remains Critical');
 const barred=await login('demo.crm.student013@example.com');
 r=await barred(p+'get_overview');ok(r.data.enrollments.some(x=>x.absent_count===5&&x.attendance_standing==='Barred'),'5/20 becomes Barred');
 const behavioral=await login('demo.crm.student016@example.com');
 r=await behavioral(p+'get_overview');ok(r.data.warnings.some(x=>x.warning_type==='Behavioral-Level'&&x.is_active),'Cross-course behavioral warning');
 console.log(`PASS ${checks} portable demo HTTP checks.`);
}finally{
 for(const c of clients)await c('logout',{},'POST').catch(()=>{});
 server.closeAllConnections();await new Promise(r=>server.close(r));
}
