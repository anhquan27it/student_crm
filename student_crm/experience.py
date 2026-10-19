"""Role workbenches and shared term filters. Read-only scoped endpoints."""
import frappe
import re
from datetime import datetime
from frappe.utils import today,add_days,cint
from student_crm.api import _identity,_faculty
from student_crm.api import _pagination


def search_pattern(value):
    text=str(value or '')[:150].strip()
    if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}',text):
        try:text=datetime.strptime(text,'%d/%m/%Y').strftime('%Y-%m-%d')
        except ValueError:pass
    return '%'+text+'%'


def term_filter(academic_term,params,column):
    if not academic_term:return ''
    if not isinstance(academic_term,str) or len(academic_term)>140 or not frappe.db.exists('Academic Term',academic_term):
        frappe.throw('Học kỳ không hợp lệ.')
    params['term']=academic_term
    return ' and '+column+'=%(term)s'


def student_metrics(academic_term,params):
    """SQL fragments are constants; all caller values are bound parameters."""
    if not academic_term:return '',"coalesce(s.risk_standing,'Good')",'s.attendance_rate','s.total_absent',''
    term_filter(academic_term,params,'academic_term')
    joins=''' left join (select student,sum(completed_sessions) as completed,sum(present_count) as present,
      sum(absent_count) as absent,max(case when status in ('Dropped','Withdrawn') then 0
        when attendance_standing='Barred' then 3 when attendance_standing='Critical' then 2
        when attendance_standing='Warning' then 1 else 0 end) as risk
      from `tabStudent Course Enrollment` where academic_term=%(term)s group by student) em on em.student=s.name
      left join (select student,max(case severity when 'Barred' then 3 when 'Critical' then 2 else 1 end) as risk,max(consecutive_sessions) as streak
      from `tabStudent Warning` where academic_term=%(term)s and is_active=1 and warning_type='Behavioral-Level' group by student) wm on wm.student=s.name '''
    risk="case greatest(coalesce(em.risk,0),coalesce(wm.risk,0)) when 3 then 'Barred' when 2 then 'Critical' when 1 then 'Warning' else 'Good' end"
    return joins,risk,'case when em.completed>0 then 100*em.present/em.completed else 0 end','coalesce(em.absent,0)',' and em.student is not null'


def advisor_dashboard(advisor_user=None,limit_start=0,page_length=50,academic_term=None,status='active'):
    user,admin=_identity();start,size=_pagination(limit_start,page_length)
    if advisor_user is not None and (not isinstance(advisor_user,str) or not advisor_user or len(advisor_user)>140):frappe.throw('Cố vấn không hợp lệ.')
    if not admin and advisor_user not in (None,user):frappe.throw('Chỉ được xem sinh viên phụ trách.',frappe.PermissionError)
    target=advisor_user if admin else user;faculty=_faculty(target,advisor=True) if target else None
    params=dict(start=start,limit=size+1);scope='1=1'
    if faculty:scope='s.advisor=%(faculty)s';params['faculty']=faculty.name
    joins,risk,rate,absent,student_term=student_metrics(academic_term,params)
    streak='coalesce(wm.streak,0)' if academic_term else 's.behavioral_absence_streak'
    student_summary=frappe.db.sql("select count(*) as total_students,sum(("+risk+")='Good') as good,sum(("+risk+")='Warning') as warning,sum(("+risk+")='Critical') as critical,sum(("+risk+")='Barred') as barred from `tabStudent` s "+joins+' where '+scope+student_term,params,as_dict=True)[0]
    if status not in ('active','all','Open','In Progress','Resolved'):frappe.throw('Trạng thái cảnh báo không hợp lệ.')
    warning_scope=scope+term_filter(academic_term,params,'w.academic_term')
    if status=='active':warning_scope+=" and w.is_active=1 and w.status in ('Open','In Progress')"
    elif status!='all':warning_scope+=' and w.status=%(warning_status)s';params['warning_status']=status
    warning_summary=frappe.db.sql('''select count(*) as active_warnings,sum(w.status='Open') as open,
      sum(w.status='In Progress') as in_progress,sum(w.warning_type='Behavioral-Level') as behavioral,
      sum(w.severity='Barred') as barred from `tabStudent Warning` w join `tabStudent` s on s.name=w.student where '''+warning_scope,params,as_dict=True)[0]
    warnings=frappe.db.sql('''select w.*,s.student_name,c.course_name from `tabStudent Warning` w
      join `tabStudent` s on s.name=w.student left join `tabCourse Offering` o on o.name=w.course_offering
      left join `tabCourse` c on c.name=o.course where '''+warning_scope+'''
      order by case w.severity when 'Barred' then 0 when 'Critical' then 1 else 2 end,w.first_detected_at,w.name
      limit %(limit)s offset %(start)s''',params,as_dict=True)
    high_risk=frappe.db.sql('select s.name as student,s.student_name,s.email,s.phone,s.advisor,('+risk+') as risk_standing,'+streak+' as behavioral_absence_streak,'+absent+' as total_absent,'+rate+' as attendance_rate,s.risk_updated_at from `tabStudent` s '+joins+' where '+scope+student_term+" and ("+risk+") in ('Critical','Barred') order by case when ("+risk+")='Barred' then 0 else 1 end,s.student_name,s.name limit %(limit)s offset %(start)s",params,as_dict=True)
    return dict(advisor_user=target,advisor=faculty.name if faculty else None,scope='advisor' if faculty else 'all',
      summary=dict(students={k:cint(v) for k,v in student_summary.items()},warnings={k:cint(v) for k,v in warning_summary.items()}),
      warnings=warnings[:size],high_risk_students=high_risk[:size],pagination=dict(limit_start=start,page_length=size,warnings_has_more=len(warnings)>size,high_risk_has_more=len(high_risk)>size))


@frappe.whitelist(methods=['GET'])
def get_terms():
    user,admin=_identity();params={};scope='1=1'
    if not admin:
        faculty=frappe.db.get_value('Faculty Member',{'user':user,'status':'Active'},['name','is_advisor','is_instructor'],as_dict=True)
        student=frappe.db.get_value('Student',{'user':user},'name');clauses=[]
        if faculty:
            params['faculty']=faculty.name
            if faculty.is_advisor:clauses.append('''exists(select 1 from `tabStudent Course Enrollment` e join `tabStudent` s on s.name=e.student where e.academic_term=t.name and s.advisor=%(faculty)s)
              or exists(select 1 from `tabStudent Support Case` c join `tabStudent` s on s.name=c.student where c.academic_term=t.name and s.advisor=%(faculty)s)''')
            if faculty.is_instructor:clauses.append('''exists(select 1 from `tabCourse Offering` o where o.academic_term=t.name and o.instructor=%(faculty)s)
              or exists(select 1 from `tabClass Session` cs join `tabCourse Offering` o on o.name=cs.course_offering where o.academic_term=t.name and cs.instructor=%(faculty)s)''')
        if student:
            params['student']=student
            clauses.append('exists(select 1 from `tabStudent Course Enrollment` e where e.academic_term=t.name and e.student=%(student)s)')
        scope='('+' or '.join('('+c+')' for c in clauses)+')' if clauses else '1=0'
    rows=frappe.db.sql('select t.name,t.term_name,t.is_current,t.start_date,t.end_date from `tabAcademic Term` t where '+scope+' order by t.is_current desc,t.start_date desc,t.name',params,as_dict=True)
    return dict(items=rows)


@frappe.whitelist(methods=['GET'])
def unread_count():
    user,admin=_identity()
    return dict(unread=frappe.db.count('Notification Log',{'for_user':user,'type':'Student CRM','read':0}))


@frappe.whitelist(methods=['GET'])
def get_workbench(academic_term=None):
    user,admin=_identity()
    from student_crm import portal,support
    params={'today':today()}
    if admin:
        student_term=''
        if academic_term:
            term_filter(academic_term,params,'academic_term')
            student_term=' and exists(select 1 from `tabStudent Course Enrollment` e where e.student=s.name and e.academic_term=%(term)s)'
        offering_term=term_filter(academic_term,params,'o.academic_term')
        summary=dict(students=frappe.db.sql('select count(*) from `tabStudent` s where 1=1'+student_term,params)[0][0],
            unassigned_students=frappe.db.sql("select count(*) from `tabStudent` s where coalesce(s.advisor,'')=''"+student_term,params)[0][0],
            unassigned_offerings=frappe.db.sql("select count(*) from `tabCourse Offering` o where coalesce(o.instructor,'')='' and o.status not in ('Completed','Cancelled')"+offering_term,params)[0][0],
            pending_sessions=frappe.db.sql("select count(*) from `tabClass Session` cs join `tabCourse Offering` o on o.name=cs.course_offering where cs.attendance_finalized=0 and cs.status not in ('Cancelled','Postponed') and cs.session_date<=%(today)s"+offering_term,params)[0][0])
        missing=frappe.db.sql("select s.name,s.student_name from `tabStudent` s where coalesce(s.advisor,'')=''"+student_term+' order by s.name limit 8',params,as_dict=True)
        offerings=frappe.db.sql("select o.name,o.class_name,o.course from `tabCourse Offering` o where coalesce(o.instructor,'')='' and o.status not in ('Completed','Cancelled')"+offering_term+' order by o.name limit 8',params,as_dict=True)
        return dict(role='admin',summary=summary,unassigned_students=missing,unassigned_offerings=offerings,
            pending_sessions=portal.list_sessions(attendance_filter='pending',academic_term=academic_term,date_scope='past',page_length=8)['items'])
    faculty=frappe.db.get_value('Faculty Member',{'user':user,'status':'Active'},['name','is_advisor','is_instructor'],as_dict=True)
    if faculty and faculty.is_advisor:
        scope,p=support._scope();p['today']=today();scope+=term_filter(academic_term,p,'c.academic_term')
        counts=frappe.db.sql('''select count(*) as active,
          sum(c.priority='Urgent') as urgent,sum(c.target_date<%(today)s) as overdue,
          sum(not exists(select 1 from `tabIntervention Log` i where i.support_case=c.name and i.contact_result='Reached')) as uncontacted
          from `tabStudent Support Case` c join `tabStudent` s on s.name=c.student where c.status!='Closed' and '''+scope,p,as_dict=True)[0]
        return dict(role='advisor',summary={k:cint(v) for k,v in counts.items()},
            overdue=support.list_cases(academic_term=academic_term,status='overdue',page_length=6)['items'],
            urgent=support.list_cases(academic_term=academic_term,status='urgent',page_length=6)['items'],
            uncontacted=support.list_cases(academic_term=academic_term,status='uncontacted',page_length=6)['items'])
    if faculty and faculty.is_instructor:
        p=dict(faculty=faculty.name,today=today());scope="coalesce(nullif(cs.instructor,''),o.instructor)=%(faculty)s"+term_filter(academic_term,p,'o.academic_term')
        counts=frappe.db.sql('''select sum(cs.session_date=%(today)s and cs.status not in ('Cancelled','Postponed')) as today_sessions,
          sum(cs.session_date<=%(today)s and cs.attendance_finalized=0 and cs.status not in ('Cancelled','Postponed')) as pending_sessions
          from `tabClass Session` cs join `tabCourse Offering` o on o.name=cs.course_offering where '''+scope,p,as_dict=True)[0]
        corrections=support.list_corrections(academic_term=academic_term,status='Pending',page_length=1)
        return dict(role='instructor',summary=dict(today_sessions=cint(counts.today_sessions),pending_sessions=cint(counts.pending_sessions),pending_corrections=corrections['total_count']),
            today_sessions=portal.list_sessions(academic_term=academic_term,date_scope='today',page_length=12)['items'],
            pending_sessions=portal.list_sessions(academic_term=academic_term,date_scope='past',attendance_filter='pending',page_length=8)['items'],
            upcoming=portal.list_sessions(academic_term=academic_term,date_scope='upcoming',page_length=6)['items'])
    student=frappe.db.get_value('Student',{'user':user},'name')
    if not student:frappe.throw('Tài khoản chưa được phân công vai trò.',frappe.PermissionError)
    detail=portal.get_student_detail(student,academic_term=academic_term)
    adviser=frappe.db.get_value('Faculty Member',{'name':detail['profile'].advisor,'status':'Active','is_advisor':1},['full_name','email','phone'],as_dict=True) if detail['profile'].advisor else None
    return dict(role='student',profile=detail['profile'],enrollments=detail['enrollments'],advisor=adviser,
        pending_requests=support.list_corrections(academic_term=academic_term,status='Pending',page_length=1)['total_count'])
