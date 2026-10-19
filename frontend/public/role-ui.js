export const roleStatusOptions={
  courses:[['all','Tất cả trạng thái'],['Planned','Dự kiến'],['Open','Mở đăng ký'],['In Progress','Đang học'],['Completed','Đã kết thúc'],['Cancelled','Đã hủy']],
  sessions:[['all','Tất cả buổi học'],['pending','Chưa chốt điểm danh'],['done','Đã chốt điểm danh']],
  students:[['all','Tất cả mức nguy cơ'],['Good','Ổn định'],['Warning','Nhắc nhở'],['Critical','Nguy hiểm'],['Barred','Cấm thi']],
  warnings:[['active','Cảnh báo đang hoạt động'],['Open','Chưa xử lý'],['In Progress','Đang hỗ trợ'],['Resolved','Đã giải quyết'],['all','Toàn bộ lịch sử']],
  cases:[['all','Tất cả hồ sơ'],['urgent','Khẩn cấp'],['overdue','Quá hạn liên hệ'],['uncontacted','Chưa liên hệ thành công'],['Open','Chưa xử lý'],['In Progress','Đang hỗ trợ'],['Monitoring','Theo dõi'],['Closed','Đã đóng']],
  interventions:[['all','Tất cả kết quả'],['Monitoring','Đang theo dõi'],['Pending','Chờ xử lý'],['Improved','Đã cải thiện'],['Escalated','Chuyển cấp hỗ trợ'],['Closed','Đã kết thúc']],
  corrections:[['all','Tất cả yêu cầu'],['Pending','Chờ duyệt'],['Approved','Đã chấp thuận'],['Rejected','Đã từ chối']],
  'my-attendance':[['all','Tất cả kết quả'],['Present','Có mặt'],['Absent','Vắng mặt'],['Late','Đi muộn']],
};

export function createRoleUI({state,esc,head,stat,icon,date,time,num,badge,empty,sessionTable}) {
  const scoped=new Set(['overview','courses','sessions','students','profile','warnings','cases','interventions','impact','corrections','my-attendance']);
  const defaultFilter=page=>page==='warnings'?'active':'all';
  const filters=page=>!scoped.has(page)?'':`<div class="scope-toolbar"><div class="field"><label for="term-filter">Học kỳ</label><select id="term-filter"><option value="">Tất cả học kỳ</option>${(state.terms||[]).map(t=>`<option value="${esc(t.name)}" ${state.term===t.name?'selected':''}>${esc((t.term_name||t.name)+(t.term_name&&t.term_name!==t.name?' · '+t.name:''))}</option>`).join('')}</select></div>${roleStatusOptions[page]?`<div class="field"><label for="page-filter">Trạng thái</label><select id="page-filter">${roleStatusOptions[page].map(([v,l])=>`<option value="${esc(v)}" ${state.filter===v?'selected':''}>${esc(l)}</option>`).join('')}</select></div>`:''}${page==='sessions'?`<div class="field"><label for="date-filter">Ngày học</label><select id="date-filter">${[['all','Tất cả ngày'],['today','Hôm nay'],['past','Đến hôm nay'],['upcoming','7 ngày sắp tới']].map(([v,l])=>`<option value="${v}" ${(state.dateScope||'all')===v?'selected':''}>${l}</option>`).join('')}</select></div>`:''}<span class="scope-note">${state.term?'Số liệu theo học kỳ đã chọn':'Số liệu tổng hợp tất cả học kỳ'}</span></div>`;
  const panel=(title,sub,body,href='')=>`<section class="panel"><div class="panel-head between"><div><h2>${title}</h2><p>${sub}</p></div>${href?`<a class="link small" href="${href}">Xem tất cả →</a>`:''}</div>${body}</section>`;
  const item=(title,description,href,tag='')=>`<a class="work-item" href="${href}"><div><div class="cell-name">${esc(title)}</div><div class="cell-sub">${esc(description)}</div></div>${tag}<span class="chevron">${icon('chevron')}</span></a>`;
  const sessions=(rows,message)=>rows.length?sessionTable(rows):empty(message,'Kiểm tra lịch học và phạm vi học kỳ đang chọn.');
  const cases=(rows,title,status)=>panel(title,{'urgent':'Liên hệ sớm để thống nhất hướng hỗ trợ','overdue':'Các lịch hẹn đã qua, hồ sơ còn mở','uncontacted':'Chưa ghi nhận lần liên hệ có kết quả thành công'}[status],rows.length?rows.map(r=>`<button class="work-item case-open" data-action="support-case" data-id="${esc(r.name)}"><div><div class="cell-name">${esc(r.student_name)}</div><div class="cell-sub">${esc(r.name)} · Hẹn ${date(r.target_date)}</div></div>${badge(r.priority,r.priority==='Urgent'?'Khẩn cấp':'Cần hỗ trợ')}${icon('chevron')}</button>`).join(''):empty('Không có hồ sơ trong nhóm này'),`#/cases?status=${status}`);
  function renderWorkbench(d) {
    if(d.role==='admin') {
      const s=d.summary;
      return head('Điều hành hệ thống','Các dữ liệu cần hoàn thiện và công việc vận hành cần xử lý.',`<a class="btn primary" href="#/students">${icon('users')} Quản lý sinh viên</a>`,'KHÔNG GIAN QUẢN TRỊ')+
        `<div class="stats">${stat('Sinh viên',s.students,'users','Theo học kỳ đang chọn')}${stat('Chưa có cố vấn',s.unassigned_students,'heart','Cần phân công phụ trách','amber')}${stat('Lớp thiếu giảng viên',s.unassigned_offerings,'book','Các lớp chưa kết thúc','red')}${stat('Buổi chưa điểm danh',s.pending_sessions,'calendar','Buổi đến hôm nay chưa chốt')}</div><div class="work-grid">`+
        panel('Phân công cố vấn','Mở sinh viên → Lịch sử cố vấn để phân công.',d.unassigned_students.length?d.unassigned_students.map(r=>item(r.student_name,r.name,'#/students/'+encodeURIComponent(r.name))).join(''):empty('Đã phân công đầy đủ'),'#/students')+
        panel('Hoàn thiện phân công giảng dạy','Cập nhật giảng viên tại danh mục Lớp học phần.',d.unassigned_offerings.length?d.unassigned_offerings.map(r=>item(r.class_name||r.name,r.course,'#/catalog?doctype=Course%20Offering')).join(''):empty('Không có lớp thiếu giảng viên'),'#/catalog?doctype=Course%20Offering')+'</div>'+panel('Buổi cần chốt điểm danh','Các buổi đã đến ngày học, chưa hủy hoặc hoãn.',sessionTable(d.pending_sessions),'#/sessions?status=pending&date_scope=past');
    }
    if(d.role==='advisor') {
      const s=d.summary;
      return head('Việc cần xử lý hôm nay','Ưu tiên liên hệ và ghi lại kết quả để tiếp tục theo dõi.',`<a class="btn" href="#/impact">${icon('trend')} Hiệu quả hỗ trợ</a>`,'KHÔNG GIAN CỐ VẤN')+
        `<div class="stats">${stat('Hồ sơ đang mở',s.active,'heart','Sinh viên được phân công')}${stat('Cần liên hệ khẩn',s.urgent,'alert','Hồ sơ ưu tiên khẩn cấp','red')}${stat('Đã quá lịch hẹn',s.overdue,'clock','Cần cập nhật lần theo dõi','amber')}${stat('Chưa liên hệ được',s.uncontacted,'phone','Chưa có lần liên hệ thành công')}</div><div class="work-grid">${cases(d.overdue,'Lịch hẹn quá hạn','overdue')}${cases(d.urgent,'Ưu tiên khẩn cấp','urgent')}</div>${cases(d.uncontacted,'Bắt đầu liên hệ','uncontacted')}`;
    }
    if(d.role==='instructor') {
      const s=d.summary;
      return head('Lịch dạy và việc cần làm','Mở buổi học để điểm danh, hoặc đối chiếu các yêu cầu của sinh viên.',`<a class="btn" href="#/corrections?status=Pending">${icon('check')} Yêu cầu chờ duyệt</a>`,'KHÔNG GIAN GIẢNG VIÊN')+
        `<div class="stats three">${stat('Buổi dạy hôm nay',s.today_sessions,'calendar',date(state.ctx.today))}${stat('Buổi còn chưa chốt',s.pending_sessions,'clock','Buổi đến hôm nay','amber')}${stat('Yêu cầu chờ duyệt',s.pending_corrections,'check','Theo các buổi được phân công','red')}</div>`+
        panel('Buổi dạy hôm nay','Ưu tiên công việc trong ngày.',sessions(d.today_sessions,'Hôm nay chưa có buổi dạy'),'#/sessions?date_scope=today')+
        `<div class="work-grid">${panel('Điểm danh còn thiếu','Hoàn thành các buổi chưa chốt.',sessions(d.pending_sessions,'Không có buổi cần chốt bổ sung'),'#/sessions?status=pending&date_scope=past')}${panel('7 ngày sắp tới','Chuẩn bị cho các buổi tiếp theo.',sessions(d.upcoming,'Chưa có buổi học trong 7 ngày tới'),'#/sessions?date_scope=upcoming')}</div>`;
    }
    const p=d.profile,enrollments=d.enrollments;
    const atRisk=enrollments.filter(e=>['Warning','Critical','Barred'].includes(e.attendance_standing));
    return head('Việc học của tôi','Biết môn cần chú ý, kiểm tra điểm danh và tìm đúng người hỗ trợ.',`<a class="btn" href="#/profile">Xem hồ sơ học tập →</a>`,'KHÔNG GIAN SINH VIÊN')+
      `<div class="stats three">${stat('Môn đang theo dõi',enrollments.length,'book','Theo học kỳ đang chọn')}${stat('Môn cần chú ý',atRisk.length,'alert','Đang có cảnh báo chuyên cần','amber')}${stat('Đề nghị đang chờ',d.pending_requests,'check','Giảng viên đang đối chiếu')}</div><div class="work-grid">`+
      panel('Bạn cần làm gì tiếp theo?',atRisk.length?'Ưu tiên kiểm tra các môn dưới đây.':'Chuyên cần đang ổn định; tiếp tục duy trì việc đến lớp.',
        atRisk.length?atRisk.map(e=>`<div class="student-action"><div class="between"><h3>${esc(e.course_name)}</h3>${badge(e.attendance_standing)}</div><p>Bạn đã vắng <strong>${num(e.absent_count)}/${num(e.total_sessions)} slot</strong> (${num(e.absent_percentage)}%). ${e.attendance_standing==='Barred'?'Đã vượt giới hạn vắng học. Hãy trao đổi với cố vấn về kế hoạch học tập.':`Còn được nghỉ tối đa <strong>${num(e.remaining_absences)} slot</strong>. Hãy ưu tiên có mặt trong các buổi tiếp theo.`}</p><a class="link" href="#/my-attendance?status=Absent">Kiểm tra buổi vắng / đề nghị đối chiếu →</a></div>`).join(''):`<div class="panel-body"><p>Bạn chưa có môn bị cảnh báo trong phạm vi đang xem.</p><a class="btn primary" href="#/my-attendance">${icon('calendar')} Xem điểm danh từng buổi</a></div>`)+
      panel('Cố vấn của bạn','Liên hệ khi gặp khó khăn trong việc theo học.',d.advisor?`<div class="panel-body advisor-contact"><span class="stat-icon">${icon('heart')}</span><h3>${esc(d.advisor.full_name)}</h3>${d.advisor.email?`<a class="contact-link" href="mailto:${esc(d.advisor.email)}">${icon('mail')} ${esc(d.advisor.email)}</a>`:'<p class="muted">Chưa có email liên hệ.</p>'}${d.advisor.phone?`<a class="contact-link" href="tel:${esc(d.advisor.phone.replace(/[^\d+]/g,''))}">${icon('phone')} ${esc(d.advisor.phone)}</a>`:''}<p class="small muted">Gửi yêu cầu sửa điểm danh khi có sai sót. Ghi nhận hỗ trợ của cố vấn không tự thay đổi điều kiện cấm thi.</p></div>`:`<div class="panel-body"><p>Chưa được phân công cố vấn. Hãy liên hệ bộ phận quản lý sinh viên của khoa.</p></div>`)+`</div>`;
  }
  return {filters,defaultFilter,renderWorkbench};
}
