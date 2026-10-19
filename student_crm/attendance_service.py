"""University attendance: derived metrics and idempotent risk signals.

Internal service only. HTTP endpoints must check permissions before calling it.
No commit here: attendance, aggregates and warnings share one transaction.
"""
from collections import defaultdict
from contextlib import contextmanager
from decimal import Decimal, ROUND_FLOOR
from hashlib import sha256
import json

import frappe
from frappe.utils import add_days, cint, getdate, now_datetime, today


def get_policy():
    settings = frappe.get_single('CRM Settings')
    return frappe._dict(
        total=cint(settings.default_total_sessions or 20),
        reminder=Decimal(str(settings.reminder_percentage or 10)),
        critical=Decimal(str(settings.critical_percentage or 15)),
        barred=Decimal(str(settings.barred_percentage or 20)),
        consecutive=cint(settings.behavioral_consecutive_sessions or 3),
        window=cint(settings.behavioral_window_days or 14),
        near_limit=cint(settings.near_limit_remaining if settings.near_limit_remaining is not None else 1),
    )


def calculate_metrics(total, completed, absent, late, policy):
    """Counts are teaching slots; one standard session has one slot."""
    if total <= 0 or not 0 <= absent <= completed <= total:
        frappe.throw('Invalid attendance totals; expected 0 <= absent <= completed <= total.')
    percentage = Decimal(absent) * 100 / Decimal(total)
    allowed = int((Decimal(total) * policy.barred / 100).to_integral_value(rounding=ROUND_FLOOR))
    remaining = max(0, allowed - absent)
    if percentage > policy.barred:
        standing = 'Barred'
    elif percentage >= policy.critical or absent > 0 and remaining <= policy.near_limit:
        standing = 'Critical'
    elif percentage >= policy.reminder:
        standing = 'Warning'
    else:
        standing = 'Good'
    return dict(total_sessions=total, completed_sessions=completed, absent_count=absent,
        present_count=completed-absent, late_count=late, absent_percentage=float(percentage),
        max_allowed_absences=allowed, remaining_absences=remaining, attendance_standing=standing,
        statistics_updated_at=now_datetime())


@contextmanager
def defer_refresh():
    """Part 3 bulk API can flush once per batch, after all writes succeed."""
    current = getattr(frappe.local, 'crm_deferred_offerings', None)
    if current is not None:
        yield
        return
    pending = set()
    frappe.local.crm_deferred_offerings = pending
    try:
        yield
    except BaseException:
        raise
    else:
        for offering in sorted(pending):
            refresh_offering(offering)
    finally:
        frappe.local.crm_deferred_offerings = None


def schedule_refresh(offering):
    pending = getattr(frappe.local, 'crm_deferred_offerings', None)
    if pending is not None:
        pending.add(offering)
    else:
        refresh_offering(offering)


def lock_students(students):
    # Current locking reads serialize cross-course risk updates for each student.
    for student in sorted(set(students)):
        frappe.db.sql('select name from `tabStudent` where name=%s for update', (student,))


def _eligible_sql():
    return """(e.enrollment_date is null or s.session_date >= e.enrollment_date)
        and (e.status not in ('Dropped','Withdrawn')
            or (e.withdrawal_date is not null and s.session_date < e.withdrawal_date))"""


def refresh_offering(offering):
    from student_crm.attendance import lock_offering
    if not offering or not frappe.db.exists('Course Offering', offering):
        return
    lock_offering(offering)
    enrollments = frappe.get_all('Student Course Enrollment', filters={'course_offering':offering},
        fields=['name','student','course_offering','academic_term'])
    if not enrollments:
        return
    students = sorted({e.student for e in enrollments})
    lock_students(students)
    policy = get_policy()
    # One aggregate read for the entire offering, not one query per student.
    rows = frappe.db.sql("""
        select e.name as enrollment, sum(s.slot_count) as completed,
            sum(case when a.status='Absent' then s.slot_count else 0 end) as absent,
            sum(case when a.status='Late' then s.slot_count else 0 end) as late
        from `tabStudent Course Enrollment` e
        join `tabClass Session` s on s.course_offering=e.course_offering
        join `tabStudent Attendance` a on a.attendance_session=s.name and a.student=e.student
        where e.course_offering=%s and s.status='Completed' and s.attendance_finalized=1
        and s.session_date<=%s and """ + _eligible_sql() + ' group by e.name',
        (offering, today()), as_dict=True)
    grouped = {r.enrollment:r for r in rows}
    offering_doc = frappe.db.get_value('Course Offering',offering,['total_slots','academic_term'],as_dict=True)
    faculty = _student_faculty(students)
    existing = _warning_map({'course_offering':offering,'warning_type':'Course-Level'})
    for enrollment in enrollments:
        r = grouped.get(enrollment.name, frappe._dict(completed=0,absent=0,late=0))
        metrics = calculate_metrics(cint(offering_doc.total_slots),cint(r.completed),cint(r.absent),cint(r.late),policy)
        # Legacy fields are hidden compatibility aliases. New frontend uses canonical fields.
        metrics.update(total_scheduled_sessions=metrics['total_sessions'],total_completed_slots=metrics['completed_sessions'],
            total_present=metrics['present_count'],total_absent=metrics['absent_count'],total_late=metrics['late_count'],
            total_excused=0,absence_percentage=metrics['absent_percentage'],
            attendance_rate=metrics['present_count']*100/metrics['completed_sessions'] if metrics['completed_sessions'] else 0,
            absent_rate=metrics['absent_count']*100/metrics['completed_sessions'] if metrics['completed_sessions'] else 0,
            warning_status='Normal' if metrics['attendance_standing']=='Good' else 'Warning')
        frappe.db.set_value('Student Course Enrollment',enrollment.name,metrics,update_modified=False)
        current = metrics['attendance_standing']
        for severity in ('Warning','Critical','Barred'):
            key = warning_key('Course-Level',enrollment.name,severity)
            active = current == severity
            if active or key in existing:
                sync_warning(existing.get(key),key,active,dict(
                    student=enrollment.student,enrollment=enrollment.name,course_offering=offering,
                    academic_term=offering_doc.academic_term,warning_type='Course-Level',severity=severity,
                    absent_slots=metrics['absent_count'],total_slots=metrics['total_sessions'],
                    absence_percentage=metrics['absent_percentage'],remaining_absences=metrics['remaining_absences'],
                    threshold=float(policy.barred if severity=='Barred' else policy.critical if severity=='Critical' else policy.reminder),
                    reason=f"{metrics['absent_count']}/{metrics['total_sessions']} slots absent; "
                        f"{metrics['remaining_absences']} further absences allowed. Standing: {current}."),faculty.get(enrollment.student))
    refresh_students(students,policy=policy)


def warning_key(kind, scope, severity):
    return sha256(json.dumps([kind,scope,severity],separators=(',',':')).encode()).hexdigest()


def _warning_map(filters):
    return {w.warning_key:w.name for w in frappe.get_all('Student Warning',filters=filters,fields=['name','warning_key'])}


def _student_faculty(students):
    return {r.name:r.advisor for r in frappe.get_all('Student',filters={'name':['in',students]},fields=['name','advisor'])}


def sync_warning(name, key, active, values, faculty):
    """Unique key + student locks ensure at most one row per scope/severity."""
    warning = frappe.get_doc('Student Warning',name) if name else frappe.new_doc('Student Warning')
    was_active = bool(warning.is_active)
    warning.update(values)
    warning.warning_key=key
    warning.is_active=int(active)
    warning.last_evaluated_at=now_datetime()
    if not name:
        warning.first_detected_at=now_datetime()
        warning.assigned_to=faculty
        warning.status='Open'
        warning.occurrence_count=1
    elif active and not was_active:
        warning.status='Open'
        warning.occurrence_count=cint(warning.occurrence_count)+1
        warning.resolved_at=None
    elif not active:
        warning.status='Resolved'
        warning.resolved_at=warning.resolved_at or now_datetime()
    warning.flags.automatic_warning=True
    warning.save(ignore_permissions=True)


def refresh_students(students, policy=None, as_of=None):
    """Batch student summaries and recent cross-course behavioral streaks."""
    if not students:
        return
    students=sorted(set(students))
    lock_students(students)
    policy=policy or get_policy()
    as_of=getdate(as_of or today())
    start=add_days(as_of,1-policy.window)  # inclusive 14 calendar days, not 15
    summaries=frappe.get_all('Student Course Enrollment',filters={'student':['in',students]},
        fields=['student','completed_sessions','present_count','absent_count','attendance_standing','status'])
    grouped=defaultdict(list)
    for row in summaries:
        grouped[row.student].append(row)
    # Include eligible finalized sessions even if a legacy attendance row is missing.
    # A missing record breaks the streak; it is never inferred to be Absent.
    recent=frappe.db.sql("""
        select e.student,s.name as class_session,s.session_date,s.start_time,s.session_no,
            o.academic_term,a.status
        from `tabStudent Course Enrollment` e
        join `tabClass Session` s on s.course_offering=e.course_offering
        join `tabCourse Offering` o on o.name=s.course_offering
        left join `tabStudent Attendance` a on a.attendance_session=s.name and a.student=e.student
        where e.student in %(students)s and s.status='Completed' and s.attendance_finalized=1
            and s.session_date between %(start)s and %(end)s and """ + _eligible_sql() + """
        order by e.student,s.session_date,s.start_time,s.session_no,s.name
    """,dict(students=students,start=start,end=as_of),as_dict=True)
    timelines=defaultdict(list)
    for row in recent:
        timelines[row.student].append(row)
    faculty=_student_faculty(students)
    existing=_warning_map({'student':['in',students],'warning_type':'Behavioral-Level'})
    rank={'Good':0,'Warning':1,'Critical':2,'Barred':3}
    for student in students:
        rows=grouped[student]
        completed=sum(cint(r.completed_sessions) for r in rows)
        present=sum(cint(r.present_count) for r in rows)
        timeline=timelines[student]
        tail=[]
        for row in reversed(timeline):
            if row.status!='Absent':
                break
            tail.append(row)
        active=len(tail)>=policy.consecutive
        current=max((r.attendance_standing or 'Good' for r in rows if r.status not in ('Dropped','Withdrawn')),key=rank.get,default='Good')
        risk=max([current,'Critical' if active else 'Good'],key=rank.get)
        frappe.db.set_value('Student',student,dict(total_absent=sum(cint(r.absent_count) for r in rows),
            attendance_rate=present*100/completed if completed else 0,risk_standing=risk,
            behavioral_absence_streak=len(tail),risk_updated_at=now_datetime()),update_modified=False)
        key=warning_key('Behavioral-Level',student,'Critical')
        if active or key in existing:
            sync_warning(existing.get(key),key,active,dict(student=student,enrollment=None,course_offering=None,
                academic_term=tail[0].academic_term if tail else None,warning_type='Behavioral-Level',severity='Critical',
                consecutive_sessions=len(tail),window_start=start,window_end=as_of,
                last_session=tail[0].class_session if tail else None,
                evidence_json=json.dumps([r.class_session for r in reversed(tail)]),
                reason=f'{len(tail)} consecutive absent class sessions across courses in {policy.window} calendar days.'),faculty.get(student))


def rebuild_all():
    """Internal migration/settings job. Paginate offerings; never commit halfway."""
    # The singleton row acts as a settings/rebuild mutex, not a public API.
    frappe.db.sql("select name from `tabDocType` where name='CRM Settings' for update")
    for row in frappe.get_all('Course Offering',pluck='name',order_by='name'):
        refresh_offering(row)
    students=frappe.get_all('Student',pluck='name')
    for offset in range(0,len(students),200):
        refresh_students(students[offset:offset+200])


def expire_behavioral_warnings():
    """Daily job: window-based signals expire even if nobody enters attendance."""
    students=sorted(set(frappe.get_all('Student Warning',filters={'warning_type':'Behavioral-Level','is_active':1},pluck='student',distinct=True)) | set(frappe.get_all('Student',filters={'behavioral_absence_streak':['>',0]},pluck='name')))
    for offset in range(0,len(students),200):
        refresh_students(students[offset:offset+200])
