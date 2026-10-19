export function createSupportUI({request,esc,icon,badge,head,stat,empty,date,num,button,state,roles,openModal,closeButton,toast,refresh,showWarning}) {
  const call=(method,data={},verb='GET')=>request('student_crm.support.'+method,data,verb);
  const labels={Open:'Chưa xử lý','In Progress':'Đang hỗ trợ',Monitoring:'Theo dõi',Closed:'Đã đóng',
    Pending:'Chờ duyệt',Approved:'Đã chấp thuận',Rejected:'Đã từ chối',Normal:'Thông thường',High:'Cao',Urgent:'Khẩn cấp',
    Present:'Có mặt',Absent:'Vắng mặt',Late:'Đi muộn',Reached:'Đã liên hệ','No Response':'Chưa phản hồi',Rescheduled:'Hẹn lại'};
  const label=x=>labels[x]||x||'—';
  const field=(name,title,value='',type='text',required=false)=>`<div class="field"><label>${esc(title)}</label><input name="${name}" type="${type}" value="${esc(value||'')}" ${required?'required':''}></div>`;
  const select=(name,title,options,value)=>`<div class="field"><label>${esc(title)}</label><select name="${name}">${options.map(x=>`<option value="${esc(x)}" ${x===value?'selected':''}>${esc(label(x))}</option>`).join('')}</select></div>`;
  const area=(name,title,value='',required=false)=>`<div class="field full"><label>${esc(title)}</label><textarea name="${name}" maxlength="5000" ${required?'required':''}>${esc(value||'')}</textarea></div>`;
  const table=(headers,rows)=>rows.length?`<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`:empty();
  const tr=cells=>'<tr>'+cells.map(c=>'<td>'+c+'</td>').join('')+'</tr>';
  const panel=(title,body,subtitle='')=>`<section class="panel"><div class="panel-head"><h2>${title}</h2>${subtitle?'<p>'+subtitle+'</p>':''}</div>${body}</section>`;
  const pageControls=data=>`<div class="table-foot between"><span>Trang ${state.page+1}${data.total_count!==undefined?' · Tổng '+num(data.total_count)+' bản ghi':''}</span><div class="flex">${state.page?button('Trang trước','prev','sm'):''}${data.has_more?button('Trang sau','next','sm'):''}</div></div>`;
  const nameCell=r=>`<div class="cell-name">${esc(r.student_name||r.student)}</div><div class="cell-sub">${esc(r.student||'')}</div>`;
  let activeCase=null,activeCorrection=null,assignment=null;

  async function render(page) {
    const paging={limit_start:state.page*50,page_length:50};
    if(page==='cases') {
      const data=await call('list_cases',paging);
      return head('Hồ sơ hỗ trợ sinh viên','Gom cảnh báo theo sinh viên và học kỳ, theo dõi một kế hoạch hỗ trợ chung.')+
        panel('Danh sách hồ sơ',table(['SINH VIÊN','HỌC KỲ','ƯU TIÊN','TIẾN ĐỘ','HẸN THEO DÕI',''],data.items.map(r=>tr([
          nameCell(r),esc(r.academic_term||'Chưa xác định'),badge(r.priority,label(r.priority)),badge(r.status,label(r.status)),
          `<span class="${r.status!=='Closed'&&r.target_date&&r.target_date<state.ctx.today?'overdue':''}">${date(r.target_date)}</span>`,
          button('Mở hồ sơ','support-case','sm','',`data-id="${esc(r.name)}"`)])))+pageControls(data));
    }
    if(page==='impact') {
      const d=await call('get_support_dashboard'),s=d.summary,m=d.measurement;
      return head('Hiệu quả hỗ trợ','Theo dõi tiến độ và tín hiệu sinh viên quay lại học sau khi được liên hệ.')+
        `<div class="stats">${stat('Hồ sơ đang mở',s.active,'heart','Trong phạm vi phụ trách')}${stat('Quá hẹn liên hệ',s.overdue,'clock','Cần ưu tiên xử lý','red')}${stat('Hồ sơ đã đóng',s.closed,'check','Có kết quả hỗ trợ')}${stat('Quay lại học',m.return_rate===null?'—':m.return_rate+'%','trend',`${m.returned_cases}/${m.matured_cases} hồ sơ đủ thời gian quan sát`,'blue')}</div>`+
        `<div class="success-box">Chỉ số quay lại học: có ít nhất một buổi Có mặt/Đi muộn trong ngày 1–14 sau lần liên hệ thành công đầu tiên. Chỉ tính hồ sơ đã đủ 14 ngày quan sát, trong tối đa ${m.limited_to_latest} hồ sơ liên hệ gần nhất. Đây là tín hiệu theo dõi, chưa chứng minh quan hệ nhân quả.</div>`+
        panel('Kết quả quan sát',table(['SINH VIÊN','LIÊN HỆ ĐẦU','CHUYÊN CẦN HIỆN TẠI','QUAY LẠI HỌC',''],d.outcomes.map(r=>tr([nameCell(r),date(r.first_contact),num(r.attendance_rate)+'%',r.returned_to_class?'Đã ghi nhận':'Chưa ghi nhận',button('Mở hồ sơ','support-case','sm','',`data-id="${esc(r.name)}"`)]))));
    }
    if(page==='corrections') {
      const d=await call('list_corrections',paging);
      return head('Yêu cầu sửa điểm danh','Đối chiếu kết quả và minh chứng. Chỉ giảng viên phụ trách hoặc quản trị viên được duyệt.',roles().student?'<a class="btn primary" href="#/my-attendance">Đề nghị sửa điểm danh</a>':'')+
        panel('Danh sách yêu cầu',table(['SINH VIÊN','MÔN / NGÀY','ĐỀ NGHỊ','TRẠNG THÁI',''],d.items.map(r=>tr([nameCell(r),esc(r.course_name)+'<div class="cell-sub">'+date(r.session_date)+'</div>',
          label(r.original_status)+' → '+label(r.requested_status),badge(r.status,label(r.status)),button('Chi tiết','support-correction','sm','',`data-id="${esc(r.name)}"`)])))+pageControls(d));
    }
    if(page==='my-attendance') {
      const d=await call('list_my_attendance',paging);
      return head('Điểm danh của tôi','Kiểm tra kết quả từng buổi. Gửi yêu cầu nếu kết quả cần được đối chiếu.')+
        panel('Kết quả điểm danh',table(['MÔN HỌC','NGÀY','KẾT QUẢ',''],d.items.map(r=>tr([esc(r.course_name),date(r.session_date),badge(r.status,label(r.status)),
          r.attendance_finalized?button('Đề nghị sửa','support-request','sm','',`data-id="${esc(r.name)}"`):'Chưa chốt'])))+pageControls(d));
    }
    if(page==='notifications') {
      const d=await call('list_notifications',paging);
      return head('Thông báo','Cảnh báo mới, lịch theo dõi và kết quả xử lý yêu cầu.')+
        panel(`${d.unread} thông báo chưa đọc`,d.items.length?`<div class="notification-list">${d.items.map(r=>`<div class="notification-item ${r.read?'':'unread'}"><div><div class="cell-name">${esc(r.subject)}</div><div class="cell-sub">${date(r.creation,true)}</div></div>${button(r.read?'Xem':'Đọc & xem','support-notification','sm','',`data-id="${esc(r.name)}"`)}</div>`).join('')}</div>`+pageControls(d):empty('Chưa có thông báo'));
    }
    if(page==='quality') {
      const d=await call('get_data_quality');
      return head('Chất lượng dữ liệu','Các bản ghi cũ chưa đủ căn cứ để liên kết đăng ký học.')+
        `<div class="error-box">Cần đối chiếu ${d.unresolved.length} bản ghi. Hệ thống không tự tạo Enrollment hoặc suy diễn việc đăng ký học từ điểm danh.</div>`+
        panel('Cần xác minh',table(['ĐIỂM DANH','SINH VIÊN','LỚP HỌC PHẦN','BUỔI HỌC','KẾT QUẢ'],d.unresolved.map(r=>tr([esc(r.attendance),esc(r.student),esc(r.course_offering||'—'),esc(r.class_session),'Cần xác minh đăng ký học']))));
    }
    return null;
  }

  async function showCase(id) {
    const token=state.loadToken,d=await call('get_case',{case:id});if(token!==state.loadToken)return;const c=d.case;activeCase=c;
    openModal(`<div class="modal-head between"><div><div class="eyebrow">${esc(c.name)}</div><h2>Hồ sơ hỗ trợ · ${esc(c.student)}</h2></div>${closeButton()}</div><div class="modal-body">`+
      `<form id="support-case-form" class="field-grid">${select('status','Tiến độ',['Open','In Progress','Monitoring','Closed'],c.status)}${select('priority','Mức ưu tiên',['Normal','High','Urgent'],c.priority)}${field('target_date','Hẹn theo dõi',c.target_date,'date')}${area('support_plan','Kế hoạch hỗ trợ',c.support_plan)}${area('resolution_summary','Kết quả hỗ trợ (bắt buộc khi đóng)',c.resolution_summary)}<div class="field full"><button class="btn primary" type="submit">Lưu hồ sơ</button></div></form>`+
      `<div class="section-label">CẢNH BÁO LIÊN QUAN</div>${d.warnings.map(w=>`<div class="case-warning"><div>${badge(w.severity)}<p>${esc(w.reason)}</p><span class="small muted">${w.is_active?'Nguy cơ còn tồn tại':'Nguy cơ đã hết hiệu lực'}</span></div>${button('Xem / Ghi can thiệp','warning','sm','',`data-id="${esc(w.name)}"`)}</div>`).join('')||empty('Chưa có cảnh báo')}`+
      `<div class="section-label">LỊCH SỬ HỖ TRỢ</div>${d.interventions.map(i=>`<div class="case-note"><strong>${esc(i.advisor_name)}</strong><p>${esc(i.summary)}</p><div class="small muted">${date(i.contacted_at,true)} · ${esc(label(i.contact_result))}</div></div>`).join('')||empty('Chưa có lần liên hệ')}</div>`);
  }

  async function action(el) {
    const a=el.dataset.action,id=el.dataset.id;
    if(a==='support-case')return showCase(id);
    if(a==='support-assignment') {
      assignment=await call('assignment_history',{student:id});
      openModal(`<div class="modal-head between"><h2>Lịch sử cố vấn · ${esc(id)}</h2>${closeButton()}</div><div class="modal-body">`+
        (roles().admin?`<form id="support-assignment-form" class="field-grid"><div class="field full"><label>Cố vấn mới</label><select name="advisor" required>${assignment.advisors.map(f=>`<option value="${esc(f.name)}" ${f.name===assignment.advisor?'selected':''}>${esc(f.full_name)}</option>`).join('')}</select></div>${area('reason','Lý do phân công','',true)}<div class="field full"><button class="btn primary" type="submit">Cập nhật phân công</button></div></form><div class="section-label">LỊCH SỬ</div>`:'')+
        table(['CỐ VẤN','TỪ','ĐẾN','LÝ DO'],assignment.items.map(r=>tr([esc(r.advisor),date(r.effective_from,true),r.effective_to?date(r.effective_to,true):'Hiện tại',esc(r.assignment_reason)])))+'</div>');return;
    }
    if(a==='support-request') {
      activeCorrection={attendance:id};
      openModal(`<div class="modal-head between"><h2>Đề nghị sửa điểm danh</h2>${closeButton()}</div><form id="support-request-form"><div class="modal-body field-grid">${select('requested_status','Kết quả đề nghị',['Present','Absent','Late'],'Present')}${field('late_minutes','Số phút đi muộn',0,'number')}${area('reason','Lý do đề nghị','',true)}${area('evidence','Mô tả minh chứng / đường dẫn minh chứng')}<div class="small muted field full">Thông tin được giảng viên đối chiếu trước khi cập nhật. Vắng mặt vẫn tính vào tỷ lệ nghỉ học cho đến khi yêu cầu được chấp thuận.</div></div><div class="modal-actions"><button class="btn primary" type="submit">Gửi yêu cầu</button></div></form>`);return;
    }
    if(a==='support-correction') {
      const r=await call('get_correction',{correction:id});activeCorrection=r;
      openModal(`<div class="modal-head between"><h2>Đối chiếu điểm danh</h2>${closeButton()}</div><div class="modal-body"><div class="small muted">${esc(r.student_name)} · ${esc(r.course_name)} · ${date(r.session_date)}</div><h3>${label(r.original_status)} → ${label(r.requested_status)}</h3><div class="case-note"><strong>Lý do</strong><p>${esc(r.reason)}</p><strong>Minh chứng</strong><p>${esc(r.evidence||'Chưa cung cấp')}</p></div>`+
        (r.status==='Pending'&&r.can_review?`<form id="support-review-form" class="field-grid">${select('decision','Quyết định',['Approved','Rejected'],'Approved')}${area('review_note','Ghi chú xử lý','',true)}<div class="field full"><button class="btn primary" type="submit">Xác nhận xử lý</button></div></form>`:`${badge(r.status,label(r.status))}<p>${esc(r.review_note||'Đang chờ giảng viên đối chiếu.')}</p>`)+`</div>`);return;
    }
    if(a==='support-notification') {
      const n=await call('get_notification',{notification:id});
      await call('mark_notification_read',{notification:id},'POST');
      if(n.document_type==='Student Support Case')return showCase(n.document_name);
      if(n.document_type==='Student Warning'){if(roles().student&&!roles().advisor&&!roles().admin)location.hash='#/profile';else await showWarning(n.document_name);return;}
      if(n.document_type==='Attendance Correction Request')return action({dataset:{action:'support-correction',id:n.document_name}});
      await refresh();
    }
  }

  async function submit(form,data) {
    if(form.id==='support-case-form')await call('update_case',{case:activeCase.name,expected_modified:activeCase.modified,...data},'POST');
    if(form.id==='support-assignment-form')await call('assign_advisor',{student:assignment.student,expected_modified:assignment.modified,...data},'POST');
    if(form.id==='support-request-form')await call('request_correction',{attendance:activeCorrection.attendance,...data,late_minutes:Number(data.late_minutes||0)},'POST');
    if(form.id==='support-review-form')await call('review_correction',{correction:activeCorrection.name,expected_modified:activeCorrection.modified,...data},'POST');
    document.querySelector('#modal').close();toast('Đã lưu thông tin.');await refresh();
  }
  return {render,action,submit};
}
