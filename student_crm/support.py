"""Student support lifecycle. Scoped APIs, transactional changes, no manual commits."""
import json
from hashlib import sha256
import frappe
from frappe.utils import add_days, cint, getdate, get_datetime, now_datetime, today, escape_html
from student_crm.experience import term_filter
from student_crm.api import _identity, _faculty, _session_access, _check_version, _pagination


def _text(value, label, required=False, maximum=5000):
    if not isinstance(value,str) or len(value)>maximum or required and not value.strip():
        frappe.throw(label+' không hợp lệ.')
    return value.strip()


def _admin():
    user,admin=_identity()
    if not admin:frappe.throw('Chỉ quản trị viên được thực hiện thao tác này.',frappe.PermissionError)
    return user


def _student_access(student, allow_self=False):
    user,admin=_identity()
    profile=frappe.get_doc('Student',student)
    if admin:return profile
    if allow_self and profile.user==user:return profile
    faculty=_faculty(user,advisor=True)
    if profile.advisor!=faculty.name:frappe.throw('Sinh viên ngoài phạm vi phụ trách.',frappe.PermissionError)
    return profile


def _scope(alias='s'):
    user,admin=_identity()
    if admin:return '1=1',{}
    faculty=_faculty(user,advisor=True)
    return alias+'.advisor=%(advisor)s',dict(advisor=faculty.name)


def _lock_student(student):
    frappe.db.sql('select name from `tabStudent` where name=%s for update',(student,))


def validate_document(doc):
    old=doc.get_doc_before_save()
    if doc.doctype=='Student Support Case':
        if not doc.flags.support_internal:
            _student_access(doc.student)
            if not old:frappe.throw('Tạo hồ sơ qua API hỗ trợ sinh viên.')
            allowed={'priority','status','target_date','support_plan','resolution_summary','closed_at'}
            if any(str(doc.get(f.fieldname) or '')!=str(old.get(f.fieldname) or '')
                   for f in doc.meta.fields if f.fieldtype not in ('Section Break','Column Break') and f.fieldname not in allowed):
                frappe.throw('Các trường định danh của hồ sơ do hệ thống quản lý.')
        if doc.status=='Closed':
            _text(doc.resolution_summary or '', 'Kết quả hỗ trợ',required=True)
            doc.closed_at=doc.closed_at or now_datetime()
        else:doc.closed_at=None
        if doc.target_date and getdate(doc.target_date)<getdate(doc.opened_at):
            frappe.throw('Ngày theo dõi không thể trước ngày mở hồ sơ.')
    elif not doc.flags.support_internal:
        frappe.throw('Bản ghi này được quản lý qua API nghiệp vụ.')


def prevent_delete(doc):
    frappe.throw('Giữ lịch sử nghiệp vụ; không xóa bản ghi này.')


def _advisor_user(advisor):
    return frappe.db.get_value('Faculty Member',{'name':advisor,'status':'Active','is_advisor':1},'user') if advisor else None


def notify(user,subject,doctype,name,key):
    if not user or not frappe.db.get_value('User',user,'enabled'):return
    event=sha256((user+'|'+key).encode()).hexdigest()
    if frappe.db.exists('Notification Log',{'crm_event_key':event}):return
    frappe.get_doc(dict(doctype='Notification Log',for_user=user,from_user=frappe.session.user,
        type='Student CRM',subject=escape_html(subject),document_type=doctype,document_name=name,
        crm_event_key=event,read=0)).insert(ignore_permissions=True)


def sync_case_task(case):
    user=_advisor_user(case.owner_advisor)
    existing=frappe.get_all('ToDo',filters={'reference_type':case.doctype,'reference_name':case.name},
        fields=['name','allocated_to','status'])
    for task in existing:
        status='Closed' if case.status=='Closed' else 'Cancelled' if task.allocated_to!=user else 'Open'
        frappe.db.set_value('ToDo',task.name,dict(status=status,date=case.target_date),update_modified=False)
    if user and case.status!='Closed' and not any(t.allocated_to==user for t in existing):
        frappe.get_doc(dict(doctype='ToDo',allocated_to=user,assigned_by=frappe.session.user,
            reference_type=case.doctype,reference_name=case.name,status='Open',priority='High',
            date=case.target_date,description='Theo dõi hồ sơ hỗ trợ '+escape_html(case.name))).insert(ignore_permissions=True)


def case_changed(doc,method=None):
    sync_case_task(doc)


def ensure_case(warning):
    key=sha256(json.dumps([warning.student,warning.academic_term or 'unassigned']).encode()).hexdigest()
    _lock_student(warning.student)
    name=frappe.db.get_value('Student Support Case',{'case_key':key},'name')
    if name:return frappe.get_doc('Student Support Case',name)
    student=frappe.get_doc('Student',warning.student)
    case=frappe.get_doc(dict(doctype='Student Support Case',student=student.name,academic_term=warning.academic_term,
        case_key=key,owner_advisor=student.advisor,status='Open',priority='Urgent' if warning.severity=='Barred' else 'High',
        opened_at=now_datetime(),target_date=add_days(today(),1),baseline_attendance_rate=student.attendance_rate))
    case.flags.support_internal=True;case.insert(ignore_permissions=True)
    return case


def warning_changed(doc,method=None):
    if not frappe.db.exists('DocType','Student Support Case'):return
    if not frappe.get_meta('Student Warning').has_field('support_case'):return
    old=doc.get_doc_before_save()
    if doc.is_active:
        case=ensure_case(doc)
        if doc.support_case!=case.name:
            frappe.db.set_value(doc.doctype,doc.name,'support_case',case.name,update_modified=False);doc.support_case=case.name
        reactivated=not old or not old.is_active or old.severity!=doc.severity
        if case.status=='Closed' and reactivated and not doc.flags.support_bootstrap:
            case.status='Open';case.resolution_summary='';case.closed_at=None
        if doc.severity=='Barred':case.priority='Urgent'
        case.owner_advisor=frappe.db.get_value('Student',doc.student,'advisor')
        case.flags.support_internal=True;case.save(ignore_permissions=True)
        sync_case_task(case)
        if reactivated:
            notify(_advisor_user(case.owner_advisor),'Cảnh báo '+doc.severity+' · '+doc.student,
                   doc.doctype,doc.name,'warning:'+doc.name+':'+str(doc.occurrence_count or 1))
            notify(frappe.db.get_value('Student',doc.student,'user'),'Có cảnh báo chuyên cần mới. Hãy liên hệ cố vấn học tập.',
                   doc.doctype,doc.name,'warning:'+doc.name+':'+str(doc.occurrence_count or 1))
    if doc.support_case:
        case=frappe.get_doc('Student Support Case',doc.support_case)
        followup_changed=old is not None and str(old.next_follow_up_date or '')!=str(doc.next_follow_up_date or '')
        if doc.next_follow_up_date and case.status!='Closed' and followup_changed:
            case.target_date=doc.next_follow_up_date;case.flags.support_internal=True;case.save(ignore_permissions=True)
        sync_case_task(case)


def intervention_changed(doc,method=None):
    if not frappe.get_meta('Intervention Log').has_field('support_case'):return
    # Keep the case captured when this contact was recorded, even if a rolling
    # behavioral warning is reused in a later academic term.
    case=doc.support_case or frappe.db.get_value('Student Warning',doc.warning,'support_case')
    if not case:return
    frappe.db.set_value(doc.doctype,doc.name,'support_case',case,update_modified=False);doc.support_case=case
    if doc.flags.support_link_only:return
    record=frappe.get_doc('Student Support Case',case)
    latest=frappe.get_all('Intervention Log',filters={'support_case':case},pluck='name',order_by='contacted_at desc,creation desc',limit_page_length=1)
    if latest and latest[0]!=doc.name:return
    if record.status!='Closed':
        record.status='Monitoring' if doc.outcome=='Improved' else 'In Progress'
        if doc.next_follow_up_date:record.target_date=doc.next_follow_up_date
        record.flags.support_internal=True;record.save(ignore_permissions=True);sync_case_task(record)


def sync_assignment(student,reason='Advisor changed on student profile',term=None):
    if not frappe.db.exists('DocType','Advisor Assignment'):return
    _lock_student(student.name)
    current=frappe.get_all('Advisor Assignment',filters={'student':student.name,'effective_to':['is','not set']},
        fields=['name','advisor'])
    if len(current)==1 and current[0].advisor==student.advisor:return
    moment=now_datetime()
    for row in current:
        record=frappe.get_doc('Advisor Assignment',row.name);record.effective_to=moment
        record.flags.support_internal=True;record.save(ignore_permissions=True)
    if student.advisor:
        if not _advisor_user(student.advisor):frappe.throw('Chọn cố vấn đang hoạt động.')
        record=frappe.get_doc(dict(doctype='Advisor Assignment',student=student.name,advisor=student.advisor,
            academic_term=term,effective_from=moment,assignment_reason=reason,recorded_by=frappe.session.user,recorded_at=moment))
        record.flags.support_internal=True;record.insert(ignore_permissions=True)
    for name in frappe.get_all('Student Support Case',filters={'student':student.name,'status':['!=','Closed']},pluck='name'):
        case=frappe.get_doc('Student Support Case',name);case.owner_advisor=student.advisor
        case.flags.support_internal=True;case.save(ignore_permissions=True);sync_case_task(case)
    # Historical intervention author never changes. Only open warning ownership follows reassignment.
    for name in frappe.get_all('Student Warning',filters={'student':student.name,'status':['in',['Open','In Progress']]},pluck='name'):
        frappe.db.set_value('Student Warning',name,'assigned_to',student.advisor,update_modified=False)


def student_changed(doc,method=None):
    old=doc.get_doc_before_save()
    if not old or old.advisor!=doc.advisor:
        sync_assignment(doc,reason=getattr(doc.flags,'assignment_reason',None) or 'Advisor changed on student profile',
                        term=getattr(doc.flags,'assignment_term',None))


@frappe.whitelist(methods=['POST'])
def assign_advisor(student,advisor,reason,academic_term=None,expected_modified=None):
    _admin();reason=_text(reason,'Lý do phân công',True,2000)
    _lock_student(student);profile=frappe.get_doc('Student',student)
    if not expected_modified:frappe.throw('Thiếu phiên bản hồ sơ sinh viên.',frappe.TimestampMismatchError)
    _check_version(profile,expected_modified)
    if not _advisor_user(advisor):frappe.throw('Chọn cố vấn đang hoạt động.')
    if academic_term and not frappe.db.exists('Academic Term',academic_term):frappe.throw('Học kỳ không tồn tại.')
    profile.advisor=advisor;profile.flags.assignment_reason=reason;profile.flags.assignment_term=academic_term
    profile.save(ignore_permissions=True)
    return dict(student=student,advisor=advisor,modified=str(profile.modified))


@frappe.whitelist(methods=['GET'])
def list_cases(limit_start=0,page_length=50,academic_term=None,status='all'):
    scope,params=_scope();start,size=_pagination(limit_start,page_length);params.update(start=start,limit=size+1,today=today())
    scope+=term_filter(academic_term,params,'c.academic_term')
    if status not in ('all','Open','In Progress','Monitoring','Closed','overdue','urgent','uncontacted'):frappe.throw('Trạng thái hồ sơ không hợp lệ.')
    if status in ('Open','In Progress','Monitoring','Closed'):scope+=' and c.status=%(case_status)s';params['case_status']=status
    if status=='overdue':scope+=" and c.status!='Closed' and c.target_date<%(today)s"
    if status=='urgent':scope+=" and c.status!='Closed' and c.priority='Urgent'"
    if status=='uncontacted':scope+=" and c.status!='Closed' and not exists(select 1 from `tabIntervention Log` i where i.support_case=c.name and i.contact_result='Reached')"
    rows=frappe.db.sql('''select c.*,s.student_name,s.risk_standing,f.full_name as advisor_name
        from `tabStudent Support Case` c join `tabStudent` s on s.name=c.student
        left join `tabFaculty Member` f on f.name=c.owner_advisor where '''+scope+'''
        order by case when c.status='Closed' then 1 else 0 end,c.target_date,c.modified desc limit %(limit)s offset %(start)s''',params,as_dict=True)
    count=frappe.db.sql('select count(*) from `tabStudent Support Case` c join `tabStudent` s on s.name=c.student where '+scope,params)[0][0]
    return dict(items=rows[:size],has_more=len(rows)>size,total_count=count)


@frappe.whitelist(methods=['GET'])
def get_case(case):
    record=frappe.get_doc('Student Support Case',case);_student_access(record.student)
    return dict(case=record.as_dict(),warnings=frappe.get_all('Student Warning',filters={'support_case':case},
        fields=['name','severity','warning_type','is_active','status','reason','course_offering']),
        interventions=frappe.db.sql('''select i.name,i.contacted_at,i.channel,i.contact_result,i.summary,i.action_plan,i.outcome,
          i.next_follow_up_date,f.full_name as advisor_name from `tabIntervention Log` i
          left join `tabFaculty Member` f on f.name=i.advisor where i.support_case=%s
          order by i.contacted_at desc limit 200''',(case,),as_dict=True))


@frappe.whitelist(methods=['POST'])
def update_case(case,status,priority='High',support_plan='',resolution_summary='',target_date=None,expected_modified=None):
    record=frappe.get_doc('Student Support Case',case);_student_access(record.student);_lock_student(record.student)
    record.reload()
    if not expected_modified:frappe.throw('Thiếu phiên bản hồ sơ.',frappe.TimestampMismatchError)
    _check_version(record,expected_modified)
    if status not in ('Open','In Progress','Monitoring','Closed') or priority not in ('Normal','High','Urgent'):
        frappe.throw('Trạng thái hoặc mức ưu tiên không hợp lệ.')
    record.update(dict(status=status,priority=priority,support_plan=_text(support_plan,'Kế hoạch hỗ trợ'),
        resolution_summary=_text(resolution_summary,'Kết quả hỗ trợ'),target_date=target_date or None))
    record.save(ignore_permissions=True);sync_case_task(record)
    return dict(name=record.name,modified=str(record.modified))


@frappe.whitelist(methods=['GET'])
def assignment_history(student):
    profile=_student_access(student)
    rows=frappe.get_all('Advisor Assignment',filters={'student':student},fields=['name','advisor','academic_term',
        'effective_from','effective_to','assignment_reason','recorded_by'],order_by='effective_from desc',limit_page_length=200)
    options=[]
    if _identity()[1]:options=frappe.get_all('Faculty Member',filters={'status':'Active','is_advisor':1},fields=['name','full_name'],limit_page_length=200)
    return dict(items=rows,student=student,modified=str(profile.modified),advisor=profile.advisor,advisors=options)


@frappe.whitelist(methods=['GET'])
def list_my_attendance(limit_start=0,page_length=50,academic_term=None,status='all'):
    user,admin=_identity();student=frappe.db.get_value('Student',{'user':user},'name')
    if not student:frappe.throw('Tài khoản chưa liên kết sinh viên.',frappe.PermissionError)
    start,size=_pagination(limit_start,page_length)
    params={'student':student,'limit':size+1,'start':start}
    scope='a.student=%(student)s'+term_filter(academic_term,params,'o.academic_term')
    if status not in ('all','Present','Absent','Late'):frappe.throw('Trạng thái điểm danh không hợp lệ.')
    if status!='all':scope+=' and a.status=%(attendance_status)s';params['attendance_status']=status
    rows=frappe.db.sql('''select a.name,a.status,a.late_minutes,a.session_date,a.attendance_session,
        c.course_name,s.attendance_finalized from `tabStudent Attendance` a
        join `tabClass Session` s on s.name=a.attendance_session
        join `tabCourse Offering` o on o.name=s.course_offering join `tabCourse` c on c.name=o.course
        where '''+scope+' order by a.session_date desc,a.name limit %(limit)s offset %(start)s',params,as_dict=True)
    return dict(items=rows[:size],has_more=len(rows)>size)


@frappe.whitelist(methods=['POST'])
def request_correction(attendance,requested_status,reason,late_minutes=0,evidence=''):
    user,admin=_identity();record=frappe.get_doc('Student Attendance',attendance)
    _student_access(record.student,allow_self=True)
    if requested_status not in ('Present','Absent','Late'):frappe.throw('Trạng thái điểm danh không hợp lệ.')
    try:minutes=int(late_minutes)
    except (TypeError,ValueError):frappe.throw('Số phút đi muộn không hợp lệ.')
    if str(minutes)!=str(late_minutes) or not 0<=minutes<=1440 or requested_status!='Late' and minutes:
        frappe.throw('Số phút đi muộn không hợp lệ.')
    reason=_text(reason,'Lý do',True);evidence=_text(evidence,'Minh chứng')
    from student_crm.attendance import lock_offering
    lock_offering(record.course_offering);record.reload()
    if not frappe.db.get_value('Class Session',record.attendance_session,'attendance_finalized'):
        frappe.throw('Chỉ đề nghị sửa buổi đã chốt điểm danh.')
    if record.status==requested_status and cint(record.late_minutes)==minutes:frappe.throw('Trạng thái đề nghị giống kết quả hiện tại.')
    if frappe.db.exists('Attendance Correction Request',{'attendance':attendance,'status':'Pending'}):frappe.throw('Bản ghi đang có yêu cầu chờ duyệt.')
    doc=frappe.get_doc(dict(doctype='Attendance Correction Request',attendance=attendance,student=record.student,
        class_session=record.attendance_session,requested_by=user,requested_at=now_datetime(),
        original_status=record.status,original_late_minutes=record.late_minutes or 0,attendance_version=record.modified,
        requested_status=requested_status,late_minutes=minutes,reason=reason,evidence=evidence,status='Pending'))
    doc.flags.support_internal=True;doc.insert(ignore_permissions=True)
    session=frappe.get_doc('Class Session',record.attendance_session)
    instructor=session.instructor or frappe.db.get_value('Course Offering',session.course_offering,'instructor')
    teacher=frappe.db.get_value('Faculty Member',instructor,'user') if instructor else None
    notify(teacher,'Có yêu cầu sửa điểm danh · '+record.student,doc.doctype,doc.name,'correction:'+doc.name)
    return dict(name=doc.name)


def _correction_scope():
    user,admin=_identity()
    if admin:return '1=1',{}
    faculty=frappe.db.get_value('Faculty Member',{'user':user,'status':'Active'},['name','is_instructor','is_advisor'],as_dict=True)
    student=frappe.db.get_value('Student',{'user':user},'name')
    clauses=[];params={}
    if faculty:
        params['faculty']=faculty.name
        if faculty.is_instructor:clauses.append("coalesce(nullif(cs.instructor,''),o.instructor)=%(faculty)s")
        if faculty.is_advisor:clauses.append('s.advisor=%(faculty)s')
    if student:clauses.append('r.student=%(student)s');params['student']=student
    if not clauses:frappe.throw('Không có quyền truy cập.',frappe.PermissionError)
    return '('+' or '.join(clauses)+')',params


@frappe.whitelist(methods=['GET'])
def list_corrections(limit_start=0,page_length=50,academic_term=None,status='all'):
    user,admin=_identity();scope,params=_correction_scope();start,size=_pagination(limit_start,page_length)
    params.update(limit=size+1,start=start)
    scope+=term_filter(academic_term,params,'o.academic_term')
    if status not in ('all','Pending','Approved','Rejected'):frappe.throw('Trạng thái yêu cầu không hợp lệ.')
    if status!='all':scope+=' and r.status=%(request_status)s';params['request_status']=status
    rows=frappe.db.sql('''select r.*,s.student_name,c.course_name,cs.session_date,
        f.user as instructor_user from `tabAttendance Correction Request` r
        join `tabStudent` s on s.name=r.student join `tabClass Session` cs on cs.name=r.class_session
        join `tabCourse Offering` o on o.name=cs.course_offering join `tabCourse` c on c.name=o.course
        left join `tabFaculty Member` f on f.name=coalesce(nullif(cs.instructor,''),o.instructor)
        where '''+scope+''' order by case when r.status='Pending' then 0 else 1 end,r.creation desc limit %(limit)s offset %(start)s''',params,as_dict=True)
    for row in rows:row['can_review']=bool(admin or row.instructor_user==user)
    count=frappe.db.sql('''select count(*) from `tabAttendance Correction Request` r join `tabStudent` s on s.name=r.student join `tabClass Session` cs on cs.name=r.class_session join `tabCourse Offering` o on o.name=cs.course_offering where '''+scope,params)[0][0]
    return dict(items=rows[:size],has_more=len(rows)>size,total_count=count)


@frappe.whitelist(methods=['POST'])
def review_correction(correction,decision,review_note,expected_modified=None):
    user,admin=_identity();record=frappe.get_doc('Attendance Correction Request',correction)
    session=_session_access(record.class_session)
    from student_crm.attendance import lock_offering
    lock_offering(session.course_offering)
    frappe.db.sql('select name from `tabAttendance Correction Request` where name=%s for update',(record.name,))
    record.reload();session=_session_access(record.class_session)
    if not expected_modified:frappe.throw('Thiếu phiên bản yêu cầu.',frappe.TimestampMismatchError)
    _check_version(record,expected_modified)
    if record.status!='Pending':frappe.throw('Yêu cầu đã được xử lý.')
    if decision not in ('Approved','Rejected'):frappe.throw('Quyết định không hợp lệ.')
    review_note=_text(review_note,'Ghi chú duyệt',True,2000)
    if decision=='Approved':
        attendance=frappe.get_doc('Student Attendance',record.attendance)
        if attendance.status!=record.original_status or cint(attendance.late_minutes)!=cint(record.original_late_minutes) or get_datetime(attendance.modified)!=get_datetime(record.attendance_version):
            frappe.throw('Điểm danh đã thay đổi sau khi gửi yêu cầu. Hãy từ chối và đề nghị gửi lại.',frappe.TimestampMismatchError)
        from student_crm.api import _roster_rows,submit_bulk_attendance
        payload=[dict(student=r.student,status=record.requested_status if r.student==record.student else r.status,
            late_minutes=cint(record.late_minutes if r.student==record.student else r.late_minutes),remarks=r.remarks or '') for r in _roster_rows(session)]
        submit_bulk_attendance(session.name,payload,str(session.modified))
    record.status=decision;record.review_note=review_note;record.reviewed_by=user;record.reviewed_at=now_datetime()
    record.flags.support_internal=True;record.save(ignore_permissions=True)
    notify(record.requested_by,'Yêu cầu sửa điểm danh đã được '+('chấp thuận' if decision=='Approved' else 'từ chối'),
           record.doctype,record.name,'review:'+record.name)
    return dict(name=record.name,status=record.status)


@frappe.whitelist(methods=['GET'])
def get_correction(correction):
    user,admin=_identity();scope,params=_correction_scope();params['correction']=correction
    rows=frappe.db.sql('''select r.*,s.student_name,c.course_name,cs.session_date,
        f.user as instructor_user,f.is_instructor,f.status as instructor_status
        from `tabAttendance Correction Request` r join `tabStudent` s on s.name=r.student
        join `tabClass Session` cs on cs.name=r.class_session
        join `tabCourse Offering` o on o.name=cs.course_offering join `tabCourse` c on c.name=o.course
        left join `tabFaculty Member` f on f.name=coalesce(nullif(cs.instructor,''),o.instructor)
        where r.name=%(correction)s and '''+scope,params,as_dict=True)
    if not rows:frappe.throw('Không có quyền xem yêu cầu hoặc yêu cầu không tồn tại.',frappe.PermissionError)
    row=rows[0];row['can_review']=bool(admin or row.instructor_user==user and row.is_instructor and row.instructor_status=='Active')
    return row


def daily_followups():
    if not frappe.db.exists('DocType','Student Support Case'):return
    cases=frappe.get_all('Student Support Case',filters={'status':['!=','Closed'],'target_date':['<=',today()]},pluck='name')
    for name in cases:
        case=frappe.get_doc('Student Support Case',name);_lock_student(case.student)
        sync_case_task(case)
        notify(_advisor_user(case.owner_advisor),'Đến hạn theo dõi hồ sơ '+case.name,case.doctype,case.name,
            'followup:'+case.name+':'+today())


@frappe.whitelist(methods=['GET'])
def list_notifications(limit_start=0,page_length=50):
    user,admin=_identity();start,size=_pagination(limit_start,page_length)
    rows=frappe.get_all('Notification Log',filters={'for_user':user,'type':'Student CRM'},
        fields=['name','subject','document_type','document_name','read','creation'],order_by='creation desc',
        limit_start=start,limit_page_length=size+1)
    return dict(items=rows[:size],has_more=len(rows)>size,unread=frappe.db.count('Notification Log',{'for_user':user,'type':'Student CRM','read':0}))


@frappe.whitelist(methods=['POST'])
def mark_notification_read(notification):
    user,admin=_identity()
    if not frappe.db.exists('Notification Log',{'name':notification,'for_user':user,'type':'Student CRM'}):
        frappe.throw('Không có quyền xem thông báo.',frappe.PermissionError)
    frappe.db.set_value('Notification Log',notification,'read',1,update_modified=False)
    return dict(name=notification)


@frappe.whitelist(methods=['GET'])
def get_notification(notification):
    user,admin=_identity()
    row=frappe.db.get_value('Notification Log',{'name':notification,'for_user':user,'type':'Student CRM'},
        ['name','subject','document_type','document_name','read','creation'],as_dict=True)
    if not row:frappe.throw('Không có quyền xem thông báo.',frappe.PermissionError)
    return row


@frappe.whitelist(methods=['GET'])
def get_support_dashboard(academic_term=None):
    scope,params=_scope();params['today']=today()
    scope+=term_filter(academic_term,params,'c.academic_term')
    summary=frappe.db.sql('''select count(*) as total,
        sum(c.status!='Closed') as active,sum(c.status='Closed') as closed,
        sum(c.status!='Closed' and c.target_date<%(today)s) as overdue
        from `tabStudent Support Case` c join `tabStudent` s on s.name=c.student where '''+scope,params,as_dict=True)[0]
    # First successful contact is the cutoff. Outcomes are observational, not causal claims.
    outcomes=frappe.db.sql('''select c.name,c.student,s.student_name,c.status,c.baseline_attendance_rate,s.attendance_rate,
        min(i.contacted_at) as first_contact,
        exists(select 1 from `tabStudent Attendance` a join `tabClass Session` cs on cs.name=a.attendance_session
          where a.student=c.student and cs.attendance_finalized=1 and cs.status='Completed'
          and a.status in ('Present','Late') and cs.session_date>date(min(i.contacted_at))
          and cs.session_date<=date_add(date(min(i.contacted_at)),interval 14 day)) as returned_to_class
        from `tabStudent Support Case` c join `tabStudent` s on s.name=c.student
        join `tabIntervention Log` i on i.support_case=c.name and i.contact_result='Reached'
        where '''+scope+''' group by c.name,c.student,s.student_name,c.status,c.baseline_attendance_rate,s.attendance_rate
        order by first_contact desc limit 200''',params,as_dict=True)
    # Report explicitly declares the bounded cohort used by the dashboard.
    matured=[x for x in outcomes if getdate(x.first_contact)<=getdate(add_days(today(),-14))]
    returned=sum(bool(x.returned_to_class) for x in matured)
    return dict(summary=summary,outcomes=outcomes,measurement=dict(observed_cases=len(outcomes),
        matured_cases=len(matured),returned_cases=returned,return_rate=round(returned*100/len(matured),1) if matured else None,
        window_days=14,limited_to_latest=200))


def reconcile_legacy_attendance(apply=False):
    """Never invent registrations. Attach only one eligible existing enrollment with matching snapshots."""
    from student_crm.attendance import eligible
    report=[]
    for row in frappe.get_all('Student Attendance',filters={'enrollment':['is','not set']},
        fields=['name','student','attendance_session','course_offering','session_date','status']):
        session=frappe.db.get_value('Class Session',row.attendance_session,['course_offering','session_date'],as_dict=True)
        candidates=[]
        if session and row.status in ('Present','Absent','Late') and (not row.course_offering or row.course_offering==session.course_offering) and (not row.session_date or getdate(row.session_date)==getdate(session.session_date)):
            candidates=[e for e in frappe.get_all('Student Course Enrollment',filters={'student':row.student,'course_offering':session.course_offering},
                fields=['name','status','enrollment_date','withdrawal_date']) if eligible(e,session.session_date)]
        result=dict(attendance=row.name,student=row.student,class_session=row.attendance_session,
            course_offering=session.course_offering if session else row.course_offering,
            action='Needs Review',enrollment=None,
            reason='No unique eligible enrollment with matching session snapshots')
        if len(candidates)==1:
            result.update(action='Verified Link' if apply else 'Can Link',enrollment=candidates[0].name)
            if apply:frappe.db.set_value('Student Attendance',row.name,'enrollment',candidates[0].name,update_modified=False)
        report.append(result)
    return report


@frappe.whitelist(methods=['GET'])
def get_data_quality():
    _admin()
    return dict(unresolved=reconcile_legacy_attendance(False))
