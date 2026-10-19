"""Scoped APIs used by the standalone Student CRM portal."""
import json
import frappe
from frappe.utils import cint, getdate, today
from student_crm.experience import term_filter, student_metrics, search_pattern
from student_crm.api import _identity, _pagination, _faculty, _check_version, get_advisor_dashboard

CATALOG = ('Student','Faculty Member','Department','Program','Academic Term','Course','Course Offering','Class Session','Student Course Enrollment','Student Attendance','Student Warning','Intervention Log')
EDITABLE = set(CATALOG)-{'Student Attendance','Student Warning','Intervention Log'}
VALUE_TYPES = {'Data','Int','Float','Percent','Date','Datetime','Time','Link','Select','Check','Small Text','Text','Long Text'}


def _profile():
    user,admin=_identity()
    faculty=frappe.db.get_value('Faculty Member',{'user':user,'status':'Active'},['name','full_name','is_advisor','is_instructor'],as_dict=True)
    student=frappe.db.get_value('Student',{'user':user},'name')
    return user,admin,faculty,student


def _admin():
    user,admin=_identity()
    if not admin:frappe.throw('Chỉ quản trị viên được thực hiện thao tác này.',frappe.PermissionError)
    return user


def _advisor_scope():
    user,admin=_identity()
    if admin:return None
    return _faculty(user,advisor=True).name


def assert_warning_access(warning):
    advisor=_advisor_scope()
    if advisor and frappe.db.get_value('Student',warning.student,'advisor')!=advisor:
        frappe.throw('Cảnh báo không thuộc sinh viên bạn phụ trách.',frappe.PermissionError)


def _teaching_scope(alias='o'):
    user,admin=_identity()
    if admin:return '1=1',{}
    faculty=_faculty(user)
    return f'({alias}.instructor=%(faculty)s or exists(select 1 from `tabClass Session` cs where cs.course_offering={alias}.name and cs.instructor=%(faculty)s))',{'faculty':faculty.name}


@frappe.whitelist(methods=['GET'])
def get_context():
    user,admin,faculty,student=_profile()
    from frappe.sessions import get_csrf_token
    return dict(user=user,full_name=frappe.db.get_value('User',user,'full_name'),admin=admin,faculty=faculty,student=student,
        csrf_token=get_csrf_token(),today=today(),roles=dict(admin=admin,instructor=admin or bool(faculty and faculty.is_instructor),advisor=admin or bool(faculty and faculty.is_advisor),student=bool(student)))


@frappe.whitelist(methods=['GET'])
def get_overview():
    user,admin,faculty,student=_profile()
    if admin or faculty and faculty.is_advisor:
        data=get_advisor_dashboard(page_length=200)
        data['recent_interventions']=_interventions(None,limit=6)
        return data
    if faculty and faculty.is_instructor:
        offerings=list_offerings(page_length=200)
        return dict(offerings=offerings['items'],sessions=list_sessions(page_length=12)['items'])
    if student:return get_student_detail(student)
    frappe.throw('Tài khoản chưa được gắn với hồ sơ giảng viên hoặc sinh viên.',frappe.PermissionError)


@frappe.whitelist(methods=['GET'])
def list_offerings(search='',limit_start=0,page_length=100,academic_term=None,status='all'):
    start,size=_pagination(limit_start,page_length);scope,params=_teaching_scope()
    scope+=term_filter(academic_term,params,'o.academic_term')
    if status not in ('all','Planned','Open','In Progress','Completed','Cancelled'):frappe.throw('Trạng thái lớp không hợp lệ.')
    if status!='all':scope+=' and o.status=%(offering_status)s';params['offering_status']=status
    params.update(search='%'+str(search)[:150]+'%',start=start,limit=size+1)
    rows=frappe.db.sql("""select o.name,o.class_name,o.course,c.course_name,o.academic_term,o.status,o.room,o.instructor,
        f.full_name as instructor_name,o.total_slots,coalesce(e.students,0) as students,
        coalesce(cs.completed,0) as completed,coalesce(cs.sessions,0) as sessions
        from `tabCourse Offering` o join `tabCourse` c on c.name=o.course
        left join `tabFaculty Member` f on f.name=o.instructor
        left join (select course_offering,count(*) as students from `tabStudent Course Enrollment` where status='Enrolled' group by course_offering) e on e.course_offering=o.name
        left join (select course_offering,count(*) as sessions,sum(case when attendance_finalized=1 then slot_count else 0 end) as completed from `tabClass Session` group by course_offering) cs on cs.course_offering=o.name
        where """+scope+""" and (o.name like %(search)s or c.course_name like %(search)s or o.class_name like %(search)s)
        order by o.modified desc,o.name limit %(limit)s offset %(start)s""",params,as_dict=True)
    return dict(items=rows[:size],has_more=len(rows)>size)


@frappe.whitelist(methods=['GET'])
def list_sessions(course_offering=None,limit_start=0,page_length=100,attendance_filter='all',search='',academic_term=None,date_scope='all'):
    start,size=_pagination(limit_start,page_length);user,admin=_identity();params=dict(start=start,limit=size+1,today=today(),search=search_pattern(search))
    scope='1=1'
    if not admin:
        faculty=_faculty(user);params['faculty']=faculty.name
        scope="coalesce(nullif(s.instructor,''),o.instructor)=%(faculty)s"
    scope+=term_filter(academic_term,params,'o.academic_term')
    if date_scope not in ('all','today','past','upcoming'):frappe.throw('Khoảng ngày không hợp lệ.')
    if date_scope=='today':scope+=' and s.session_date=%(today)s'
    if date_scope=='past':scope+=' and s.session_date<=%(today)s'
    if date_scope=='upcoming':
        from frappe.utils import add_days
        scope+=' and s.session_date>%(today)s and s.session_date<=%(upcoming_end)s';params['upcoming_end']=add_days(today(),7)
    if course_offering:
        scope+=' and o.name=%(offering)s';params['offering']=course_offering
    if attendance_filter not in ('all','done','pending'):frappe.throw('Bộ lọc không hợp lệ.')
    if attendance_filter=='done':scope+=' and s.attendance_finalized=1'
    if attendance_filter=='pending':scope+=" and s.attendance_finalized=0 and s.status not in ('Cancelled','Postponed')"
    scope+=' and (s.name like %(search)s or c.course_name like %(search)s or cast(s.session_date as char) like %(search)s or o.name like %(search)s or o.class_name like %(search)s)'
    rows=frappe.db.sql("""select s.name,s.course_offering,s.session_no,s.session_date,s.start_time,s.end_time,s.room,s.status,
        s.attendance_finalized,s.slot_count,s.topic,c.course_name,o.course,o.class_name,
        f.full_name as instructor_name
        from `tabClass Session` s join `tabCourse Offering` o on o.name=s.course_offering
        join `tabCourse` c on c.name=o.course
        left join `tabFaculty Member` f on f.name=coalesce(nullif(s.instructor,''),o.instructor)
        where """+scope+""" order by case when s.session_date=%(today)s then 0 when s.session_date>%(today)s then 1 else 2 end,
        case when s.session_date>=%(today)s then s.session_date end asc,
        case when s.session_date<%(today)s then s.session_date end desc,s.start_time,s.session_no
        limit %(limit)s offset %(start)s""",params,as_dict=True)
    return dict(items=rows[:size],has_more=len(rows)>size)


@frappe.whitelist(methods=['GET'])
def list_students(search='',limit_start=0,page_length=100,risk_standing='all',academic_term=None):
    advisor=_advisor_scope();start,size=_pagination(limit_start,page_length)
    params=dict(search='%'+str(search)[:150]+'%',start=start,limit=size+1);scope='1=1'
    if advisor:scope='s.advisor=%(advisor)s';params['advisor']=advisor
    joins,risk_sql,rate_sql,absent_sql,term_scope=student_metrics(academic_term,params)
    streak_sql='coalesce(wm.streak,0)' if academic_term else 's.behavioral_absence_streak'
    scope+=term_scope
    if risk_standing not in ('all','Good','Warning','Critical','Barred'):frappe.throw('Bộ lọc nguy cơ không hợp lệ.')
    if risk_standing!='all':scope+=' and ('+risk_sql+')=%(risk)s';params['risk']=risk_standing
    rows=frappe.db.sql("""select s.name,s.student_name,s.email,s.phone,s.program,s.student_status,"""+risk_sql+""" as risk_standing,
        """+rate_sql+""" as attendance_rate,"""+streak_sql+""" as behavioral_absence_streak,s.advisor,f.full_name as advisor_name
        from `tabStudent` s left join `tabFaculty Member` f on f.name=s.advisor """+joins+"""
        where """+scope+""" and (s.student_name like %(search)s or s.name like %(search)s)
        order by s.modified desc,s.name limit %(limit)s offset %(start)s""",params,as_dict=True)
    count=frappe.db.sql('''select count(*) from `tabStudent` s '''+joins+' where '+scope+'''
        and (s.student_name like %(search)s or s.name like %(search)s)''',params)[0][0]
    return dict(items=rows[:size],has_more=len(rows)>size,total_count=count,scoped_to_advisor=bool(advisor))


def _interventions(student=None,limit=50,start=0,academic_term=None,status='all'):
    advisor=_advisor_scope();params=dict(limit=limit,start=start);scope='1=1'
    if advisor:scope+=' and s.advisor=%(advisor)s';params['advisor']=advisor
    if student:scope+=' and s.name=%(student)s';params['student']=student
    scope+=term_filter(academic_term,params,'w.academic_term')
    if status not in ('all','Monitoring','Pending','Improved','Escalated','Closed'):frappe.throw('Kết quả theo dõi không hợp lệ.')
    if status!='all':scope+=' and i.outcome=%(outcome)s';params['outcome']=status
    return frappe.db.sql("""select i.name,i.warning,i.student,s.student_name,i.advisor,f.full_name as advisor_name,
        i.contacted_at,i.channel,i.contact_result,i.summary,i.action_plan,i.outcome,i.next_follow_up_date
        from `tabIntervention Log` i join `tabStudent` s on s.name=i.student
        join `tabStudent Warning` w on w.name=i.warning
        left join `tabFaculty Member` f on f.name=i.advisor
        where """+scope+" order by i.contacted_at desc limit %(limit)s offset %(start)s",params,as_dict=True)


@frappe.whitelist(methods=['GET'])
def list_interventions(limit_start=0,page_length=50,academic_term=None,status='all'):
    start,size=_pagination(limit_start,page_length)
    rows=_interventions(limit=size+1,start=start,academic_term=academic_term,status=status)
    return dict(items=rows[:size],has_more=len(rows)>size)


@frappe.whitelist(methods=['GET'])
def get_student_detail(student,academic_term=None):
    user,admin,faculty,own=_profile()
    profile=frappe.db.get_value('Student',student,['name','student_name','email','phone','program','department','advisor','student_status','risk_standing','attendance_rate','total_absent','behavioral_absence_streak','date_of_birth','enrollment_date'],as_dict=True)
    if not profile:frappe.throw('Không tìm thấy sinh viên.',frappe.DoesNotExistError)
    can_advise=admin or bool(faculty and faculty.is_advisor and profile.advisor==faculty.name)
    if not can_advise and own!=student:frappe.throw('Không có quyền xem sinh viên này.',frappe.PermissionError)
    enrollments=frappe.db.sql("""select e.name,e.course_offering,c.course_name,e.course,e.academic_term,e.status,
        e.total_sessions,e.completed_sessions,e.absent_count,e.absent_percentage,e.remaining_absences,e.attendance_standing
        from `tabStudent Course Enrollment` e left join `tabCourse` c on c.name=e.course
        where e.student=%s order by e.academic_term desc,e.course""",(student,),as_dict=True)
    warnings=frappe.get_all('Student Warning',filters={'student':student},fields=['name','warning_type','severity','is_active','status','reason','first_detected_at','next_follow_up_date'],order_by='first_detected_at desc',limit=100)
    if academic_term:
        p={'student':student};joins,risk_sql,rate_sql,absent_sql,term_scope=student_metrics(academic_term,p)
        streak_sql='coalesce(wm.streak,0)'
        metrics=frappe.db.sql('select '+streak_sql+' as behavioral_absence_streak,'+risk_sql+' as risk_standing,'+rate_sql+' as attendance_rate,'+absent_sql+' as total_absent from `tabStudent` s '+joins+' where s.name=%(student)s',p,as_dict=True)[0]
        profile.update(metrics)
        enrollments=[e for e in enrollments if e.academic_term==academic_term]
        warnings=frappe.get_all('Student Warning',filters={'student':student,'academic_term':academic_term},fields=['name','warning_type','severity','is_active','status','reason','first_detected_at','next_follow_up_date'],order_by='first_detected_at desc',limit=100)
    return dict(profile=profile,enrollments=enrollments,warnings=warnings,interventions=_interventions(student,academic_term=academic_term) if can_advise else [],can_advise=can_advise)


@frappe.whitelist(methods=['GET'])
def get_warning_detail(warning):
    doc=frappe.get_doc('Student Warning',warning);assert_warning_access(doc)
    fields=['name','student','warning_type','severity','status','is_active','reason','course_offering','enrollment','absence_percentage','absent_slots','total_slots','remaining_absences','consecutive_sessions','first_detected_at','assigned_to','follow_up_notes','next_follow_up_date','modified']
    return dict(warning={f:doc.get(f) for f in fields},student=frappe.db.get_value('Student',doc.student,['student_name','email','phone'],as_dict=True),interventions=[x for x in _interventions(doc.student) if x.warning==doc.name])


@frappe.whitelist(methods=['POST'])
def save_intervention(warning,summary,channel='Phone',contact_result='Reached',action_plan='',next_follow_up_date=None,outcome='Monitoring',contacted_at=None):
    user,admin=_identity();doc=frappe.get_doc('Student Warning',warning);assert_warning_access(doc)
    if not isinstance(summary,str) or not summary.strip() or len(summary)>5000:frappe.throw('Nội dung trao đổi cần từ 1 đến 5000 ký tự.')
    if not isinstance(action_plan,str) or len(action_plan)>5000:frappe.throw('Kế hoạch hỗ trợ quá dài.')
    if admin:
        advisor=doc.assigned_to or frappe.db.get_value('Student',doc.student,'advisor') or frappe.db.get_value('Faculty Member',{'user':user,'is_advisor':1,'status':'Active'},'name')
    else:advisor=_faculty(user,advisor=True).name
    if not advisor:frappe.throw('Hãy phân công cố vấn cho cảnh báo trước khi ghi can thiệp.')
    from frappe.utils import now_datetime
    log=frappe.get_doc(dict(doctype='Intervention Log',warning=warning,advisor=advisor,summary=summary.strip(),channel=channel,
        contact_result=contact_result,action_plan=action_plan,next_follow_up_date=next_follow_up_date or None,
        outcome=outcome,contacted_at=contacted_at or now_datetime()))
    log.insert(ignore_permissions=True)
    return dict(name=log.name,warning=warning,status=frappe.db.get_value('Student Warning',warning,'status'))


@frappe.whitelist(methods=['POST'])
def update_warning(warning,status,follow_up_notes='',next_follow_up_date=None,expected_modified=None):
    doc=frappe.get_doc('Student Warning',warning);assert_warning_access(doc)
    if status not in ('Open','In Progress','Resolved'):frappe.throw('Trạng thái không hợp lệ.')
    if not isinstance(follow_up_notes,str) or len(follow_up_notes)>5000:frappe.throw('Ghi chú không hợp lệ.')
    _check_version(doc,expected_modified)
    doc.status=status;doc.follow_up_notes=follow_up_notes;doc.next_follow_up_date=next_follow_up_date or None
    doc.save(ignore_permissions=True)
    return dict(name=doc.name,status=doc.status,modified=doc.modified)


@frappe.whitelist(methods=['GET'])
def get_settings():
    _admin();doc=frappe.get_single('CRM Settings')
    return {f.fieldname:doc.get(f.fieldname) for f in doc.meta.fields if f.fieldtype in VALUE_TYPES}


def _json_object(data):
    if isinstance(data,str):
        try:data=json.loads(data)
        except ValueError:frappe.throw('JSON không hợp lệ.')
    if not isinstance(data,dict):frappe.throw('Dữ liệu phải là một object.')
    return data


@frappe.whitelist(methods=['POST'])
def save_settings(data):
    _admin();data=_json_object(data);doc=frappe.get_single('CRM Settings')
    allowed={f.fieldname for f in doc.meta.fields if f.fieldtype in VALUE_TYPES and not f.read_only}
    if set(data)-allowed:frappe.throw('Có trường cấu hình không được phép thay đổi.')
    doc.update(data);doc.save(ignore_permissions=True)
    return get_settings()


@frappe.whitelist(methods=['GET'])
def get_catalog(doctype='Course',search='',limit_start=0,page_length=50):
    _admin()
    if doctype not in CATALOG:frappe.throw('Danh mục không được hỗ trợ.')
    start,size=_pagination(limit_start,page_length);meta=frappe.get_meta(doctype)
    fields=[f for f in meta.fields if f.fieldtype in VALUE_TYPES and not f.hidden]
    editable=[dict(name=f.fieldname,label=f.label,type=f.fieldtype,options=f.options,required=cint(f.reqd),default=f.default) for f in fields if not f.read_only]
    columns=[f.fieldname for f in fields if f.in_list_view]+[f.fieldname for f in fields if f.fieldname.endswith('_name')]
    columns=list(dict.fromkeys(['name']+columns+(['status'] if meta.has_field('status') else [])))[:7]
    filters=[]
    if search:filters=[['name','like','%'+str(search)[:150]+'%']]
    rows=frappe.get_all(doctype,filters=filters,fields=list(dict.fromkeys(['modified']+columns+[f['name'] for f in editable])),limit_start=start,limit_page_length=size+1,order_by='modified desc,name')
    return dict(doctype=doctype,items=rows[:size],columns=columns,fields=editable,editable=doctype in EDITABLE,has_more=len(rows)>size)


@frappe.whitelist(methods=['POST'])
def save_record(doctype,data,name=None,expected_modified=None):
    _admin()
    if doctype not in EDITABLE:frappe.throw('Loại bản ghi này chỉ được cập nhật qua luồng nghiệp vụ tương ứng.')
    data=_json_object(data);meta=frappe.get_meta(doctype)
    allowed={f.fieldname for f in meta.fields if f.fieldtype in VALUE_TYPES and not f.hidden and not f.read_only}
    if set(data)-allowed:frappe.throw('Payload chứa trường không được phép cập nhật.')
    doc=frappe.get_doc(doctype,name) if name else frappe.new_doc(doctype)
    if name:
        if not expected_modified:frappe.throw('Thiếu phiên bản bản ghi. Hãy tải lại trước khi sửa.',frappe.TimestampMismatchError)
        _check_version(doc,expected_modified)
    doc.update(data);doc.save(ignore_permissions=True)
    return dict(name=doc.name)


@frappe.whitelist(methods=['GET'])
def link_options(doctype,search=''):
    _admin()
    if doctype not in CATALOG+('User',):frappe.throw('Link không được hỗ trợ.')
    return frappe.get_all(doctype,filters={'name':['like','%'+str(search)[:100]+'%']},pluck='name',limit=200,order_by='name')
