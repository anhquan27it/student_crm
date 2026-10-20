// Private snapshot restore QA. Credentials arrive only on stdin.
import assert from 'node:assert/strict';
import {createInterface} from 'node:readline';
const input=createInterface({input:process.stdin,terminal:false});
const config=JSON.parse(await new Promise(r=>input.once('line',r)));input.close();process.stdin.pause();
process.env.FRAPPE_SITE=config.site;process.env.FRAPPE_URL=config.upstream;
const {server}=await import('../server.mjs');await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;let checks=0;
const ok=(v,label)=>{assert.ok(v,label);checks++;console.log('PASS '+label);};
function client(){const cookies=new Map();let csrf='';return async(method,data={},verb='GET')=>{
 const url=new URL('/api/method/'+method,base);if(verb==='GET')for(const[k,v]of Object.entries(data))url.searchParams.set(k,v);
 const r=await fetch(url,{method:verb,headers:{cookie:[...cookies].map(([k,v])=>k+'='+v).join('; '),'content-type':'application/json',...(verb==='POST'&&csrf?{'x-frappe-csrf-token':csrf}:{})},body:verb==='POST'?JSON.stringify(data):undefined});
 for(const cookie of r.headers.getSetCookie()){const pair=cookie.split(';')[0],n=pair.indexOf('=');cookies.set(pair.slice(0,n),pair.slice(n+1));}
 const body=await r.json();if(method==='student_crm.portal.get_context'&&r.ok)csrf=body.message.csrf_token;
 return {status:r.status,data:body.message,body};
};}
const clients=[];
async function login(user,password=config.password){const c=client();clients.push(c);ok((await c('login',{usr:user,pwd:password},'POST')).status===200,'Login '+user);await c('student_crm.portal.get_context');return c;}
try{
 const p='student_crm.portal.',s='student_crm.support.',a='student_crm.api.';
 ok((await fetch(base)).status===200,'Restored frontend available');
 const admin=await login('Administrator',config.admin_password);
 let r=await admin(p+'list_students');ok(r.data.total_count===121,'All 121 source students restored');
 r=await admin(p+'list_interventions');ok(r.data.items.length===36,'All 36 original intervention records restored');
 ok(r.data.items.some(x=>x.student_name==='Đặng Ngọc Tuấn'),'Original student name from screenshot preserved');
 ok(r.data.items.some(x=>x.summary.includes('Đã trao đổi và thống nhất kế hoạch theo dõi chuyên cần')),'Original intervention text preserved');
 ok((await admin(s+'list_cases',{page_length:200,status:'all'})).data.items.length===72,'All 72 support cases restored');
 ok((await admin(p+'list_offerings',{page_length:100})).data.items.length===43,'All 43 source class offerings restored');
 const advisor=await login('demo.crm.faculty01@example.com');
 ok((await advisor(p+'list_students')).data.total_count===34,'Original advisor assignment scope');
 const teacher=await login('demo.crm.faculty04@example.com');
 ok((await teacher(p+'list_offerings')).data.items.length===6,'Original instructor classes');
 r=await teacher(a+'get_session_roster',{class_session:'DEMO-20261019-CEA201-S01'});
 ok(r.data.count===8,'Original eight-student roster preserved');
 const student=await login('demo.crm.student001@example.com');
 r=await student(p+'get_overview');ok(r.data.enrollments.length===5,'Student enrollment data preserved');
 ok(r.data.interventions.length===0,'Private advisor notes remain private');
 ok((await student(s+'list_my_attendance')).data.items.length===40,'Student attendance preserved');
 ok((await student(a+'get_advisor_dashboard')).status===403,'Student role boundaries preserved');
 const last=await login('demo.crm.student100@example.com');
 ok((await last(p+'get_overview')).data.enrollments.length===5,'Student 100 data and login preserved');
 console.log(`PASS ${checks} full-copy HTTP checks.`);
}finally{
 for(const c of clients)await c('logout',{},'POST').catch(()=>{});
 server.closeAllConnections();await new Promise(r=>server.close(r));
}
