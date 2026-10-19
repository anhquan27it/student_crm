import test from 'node:test';
import assert from 'node:assert/strict';
import {createRoleUI} from '../public/role-ui.js';

function fixture(){
  const state={term:'TERM-A',terms:[{name:'TERM-A',term_name:'Học kỳ A'}],filter:'overdue',ctx:{today:'2026-10-19'}};
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  return createRoleUI({state,esc,head:(a,b)=>a+b,stat:(a,b)=>a+String(b),icon:()=>'',date:v=>v||'—',time:v=>v,
    num:v=>String(v??0),badge:v=>v,empty:t=>t||'Empty',sessionTable:rows=>'Sessions:'+rows.length});
}
test('Shared filters retain semester and case status and distinguish warning defaults',()=>{
  const ui=fixture(),html=ui.filters('cases');
  assert.match(html,/value="TERM-A" selected/);assert.match(html,/value="overdue" selected/);
  assert.match(html,/Quá hạn liên hệ/);assert.equal(ui.defaultFilter('warnings'),'active');
  assert.equal(ui.filters('roster'),'');assert.equal(ui.filters('settings'),'');
});
test('All role workbenches show their own work rather than a shared admin/advisor dashboard',()=>{
  const ui=fixture();
  assert.match(ui.renderWorkbench({role:'admin',summary:{},unassigned_students:[],unassigned_offerings:[],pending_sessions:[]}),/Điều hành hệ thống/);
  assert.match(ui.renderWorkbench({role:'advisor',summary:{},overdue:[],urgent:[],uncontacted:[]}),/Việc cần xử lý hôm nay/);
  assert.match(ui.renderWorkbench({role:'instructor',summary:{},today_sessions:[],pending_sessions:[],upcoming:[]}),/Lịch dạy và việc cần làm/);
});
test('Student guidance distinguishes risk from eligibility and escapes course names',()=>{
  const ui=fixture();
  const html=ui.renderWorkbench({role:'student',profile:{},advisor:{full_name:'Advisor',email:'advisor@example.com'},pending_requests:0,
    enrollments:[{course_name:'<PRF192>',attendance_standing:'Critical',absent_count:3,total_sessions:20,absent_percentage:15,remaining_absences:1}]});
  assert.match(html,/Còn được nghỉ tối đa <strong>1 slot/);assert.match(html,/&lt;PRF192&gt;/);
  assert.ok(!html.includes('<PRF192>'));assert.match(html,/mailto:advisor@example.com/);
  assert.match(html,/#\/my-attendance\?status=Absent/);
});
test('Student without an advisor receives a clear next step',()=>{
  const html=fixture().renderWorkbench({role:'student',profile:{},advisor:null,pending_requests:0,enrollments:[]});
  assert.match(html,/Chưa được phân công cố vấn/);assert.match(html,/bộ phận quản lý sinh viên/);
});
