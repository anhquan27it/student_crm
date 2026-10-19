"""Authenticated Student CRM endpoints for the standalone frontend.

Authorization is deliberately scoped here. Faculty profiles do not grant broad
DocType REST access. Internal reads/ignore_permissions writes follow explicit
session ownership checks and do not accept caller-selected document fields.
"""
from uuid import uuid4
import json

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, today

from student_crm.attendance import eligible, lock_offering
from student_crm.attendance_service import defer_refresh

VALID_STATUSES = {'Present', 'Absent', 'Late'}
MAX_ROSTER_SIZE = 1000
MAX_PAYLOAD_BYTES = 1_000_000


def _identity():
    user = frappe.session.user
    if not user or user == 'Guest' or not frappe.db.get_value('User', user, 'enabled'):
        frappe.throw(_('Authentication required.'), frappe.PermissionError)
    admin = user == 'Administrator' or 'System Manager' in frappe.get_roles(user)
    return user, admin


def _faculty(user, advisor=False):
    profile = frappe.db.get_value('Faculty Member', {'user':user, 'status':'Active'},
        ['name','user','is_instructor','is_advisor'], as_dict=True)
    if not profile or not profile.get('is_advisor' if advisor else 'is_instructor'):
        frappe.throw(_('An active faculty profile with the required assignment is needed.'), frappe.PermissionError)
    return profile


def _session_access(class_session):
    user, admin = _identity()
    if not isinstance(class_session, str) or not class_session.strip() or len(class_session) > 140:
        frappe.throw(_('A valid class_session is required.'))
    # Authenticate profile first, so non-faculty callers cannot probe session IDs.
    faculty = None if admin else _faculty(user)
    session = frappe.get_doc('Class Session', class_session)
    instructor = session.instructor or frappe.db.get_value('Course Offering', session.course_offering, 'instructor')
    if not admin and instructor != faculty.name:
        frappe.throw(_('You are not assigned to teach this session.'), frappe.PermissionError)
    return session


def _roster_rows(session):
    # Single joined read: roster, current-session attendance, cached course totals.
    rows = frappe.db.sql("""
        select e.name as enrollment,e.student,s.student_name,s.id_student,
            e.status as enrollment_status,e.enrollment_date,e.withdrawal_date,
            e.total_sessions,e.completed_sessions,e.absent_count,e.absent_percentage,
            e.remaining_absences,e.attendance_standing,e.statistics_updated_at,
            a.name as attendance,a.status,a.late_minutes,a.remarks
        from `tabStudent Course Enrollment` e
        join `tabStudent` s on s.name=e.student
        left join `tabStudent Attendance` a
            on a.student=e.student and a.attendance_session=%s
        where e.course_offering=%s
        order by s.student_name,e.student
    """, (session.name,session.course_offering), as_dict=True)
    # eligible() uses `status` for enrollment; attendance `status` must stay separate.
    return [r for r in rows if eligible(frappe._dict(status=r.enrollment_status,
        enrollment_date=r.enrollment_date,withdrawal_date=r.withdrawal_date),session.session_date)]


def _roster_response(session, rows=None):
    rows = _roster_rows(session) if rows is None else rows
    students = [{k:r.get(k) for k in (
        'enrollment','student','student_name','id_student','attendance','status','late_minutes','remarks',
        'total_sessions','completed_sessions','absent_count','absent_percentage',
        'remaining_absences','attendance_standing','statistics_updated_at')} for r in rows]
    return dict(session=dict(name=session.name,course_offering=session.course_offering,
        session_date=session.session_date,start_time=session.start_time,end_time=session.end_time,
        slot_count=session.slot_count,status=session.status,attendance_finalized=cint(session.attendance_finalized),
        modified=str(session.modified)), count=len(students), students=students)


@frappe.whitelist(methods=['GET'])
def get_session_roster(class_session):
    """Assigned instructor/System Manager only. Missing attendance has status null."""
    return _roster_response(_session_access(class_session))


def _parse_attendance(attendance_data):
    if isinstance(attendance_data, str):
        if len(attendance_data.encode('utf-8')) > MAX_PAYLOAD_BYTES:
            frappe.throw(_('Attendance payload is too large.'))
        try:
            attendance_data = json.loads(attendance_data)
        except (ValueError, TypeError):
            frappe.throw(_('attendance_data must be a JSON array.'))
    if not isinstance(attendance_data, list) or not 1 <= len(attendance_data) <= MAX_ROSTER_SIZE:
        frappe.throw(_('attendance_data must contain between 1 and 1000 students.'))
    normalized = {}
    for number, item in enumerate(attendance_data, 1):
        if not isinstance(item, dict) or set(item)-{'student','status','late_minutes','remarks'}:
            frappe.throw(_('Row {0} contains unsupported fields.').format(number))
        student, status = item.get('student'), item.get('status')
        if not isinstance(student,str) or not student or len(student)>140:
            frappe.throw(_('Row {0} needs a valid student ID.').format(number))
        if not isinstance(status,str) or status not in VALID_STATUSES:
            frappe.throw(_('Only Present, Absent and Late are accepted.'))
        if student in normalized:
            frappe.throw(_('A student appears more than once in the attendance payload.'))
        minutes = item.get('late_minutes',0)
        if isinstance(minutes,bool) or not isinstance(minutes,int) or not 0 <= minutes <= 1440:
            frappe.throw(_('late_minutes must be an integer from 0 to 1440.'))
        if status != 'Late' and minutes:
            frappe.throw(_('late_minutes is only accepted for Late status.'))
        if 'remarks' in item and (not isinstance(item['remarks'],str) or len(item['remarks'])>2000):
            frappe.throw(_('remarks must be text of at most 2000 characters.'))
        normalized[student] = dict(student=student,status=status,late_minutes=minutes)
        if 'remarks' in item:
            normalized[student]['remarks'] = item['remarks']
    if len(json.dumps(list(normalized.values()),ensure_ascii=False).encode('utf-8')) > MAX_PAYLOAD_BYTES:
        frappe.throw(_('Attendance payload is too large.'))
    return normalized


def _row_matches(existing, incoming):
    return existing.status == incoming['status'] and cint(existing.late_minutes) == incoming['late_minutes'] and (
        'remarks' not in incoming or (existing.remarks or '') == incoming['remarks'])


def _check_version(session, expected_modified):
    if expected_modified is None:
        return
    if not isinstance(expected_modified,str) or not expected_modified or len(expected_modified)>40:
        frappe.throw(_('expected_modified must be the version returned by get_session_roster.'))
    try:
        matches = get_datetime(session.modified) == get_datetime(expected_modified)
    except (TypeError,ValueError,OverflowError):
        frappe.throw(_('Invalid expected_modified timestamp.'))
    if not matches:
        frappe.throw(_('Attendance changed since you loaded it. Reload the roster before submitting.'), frappe.TimestampMismatchError)


@frappe.whitelist(methods=['POST'])
def submit_bulk_attendance(class_session, attendance_data, expected_modified=None):
    """Replace the complete eligible roster and finalize atomically.

    Exact retries are idempotent. Changing a finalized session requires its current
    `modified` version; corrections unfinalize/refinalize inside one transaction.
    The HTTP layer commits only after this function returns successfully.
    """
    session = _session_access(class_session)
    payload = _parse_attendance(attendance_data)
    lock_offering(session.course_offering)
    frappe.db.sql('select name from `tabClass Session` where name=%s for update',(session.name,))
    session.reload()
    # Reauthorize after locks, in case the session assignment changed concurrently.
    session = _session_access(session.name)
    if session.status in ('Cancelled','Postponed') or getdate(session.session_date)>getdate(today()):
        frappe.throw(_('Attendance may only be finalized for a non-cancelled session on or before today.'))
    roster = _roster_rows(session)
    by_student = {r.student:r for r in roster}
    if set(payload) != set(by_student):
        frappe.throw(_('Submit exactly one record for every eligible student in the roster.'))
    existing = {r.student:r for r in frappe.get_all('Student Attendance',
        filters={'attendance_session':session.name},fields=['name','student','status','late_minutes','remarks'])}
    if set(existing)-set(by_student):
        frappe.throw(_('This session contains attendance outside the eligible roster. Ask an administrator to review it.'))
    unchanged = set(existing)==set(payload) and all(_row_matches(existing[s],payload[s]) for s in payload)
    if session.attendance_finalized and unchanged:
        response = _roster_response(session,roster)
        response.update(created=0,updated=0,idempotent=True)
        return response
    _check_version(session,expected_modified)
    if session.attendance_finalized and expected_modified is None:
        frappe.throw(_('A current expected_modified version is required to correct finalized attendance.'),frappe.TimestampMismatchError)
    savepoint='crm_api_'+uuid4().hex
    frappe.db.savepoint(savepoint)
    created=updated=0
    try:
        with defer_refresh():
            if session.attendance_finalized:
                session.attendance_finalized=0
                session.save(ignore_permissions=True)
            for student,incoming in payload.items():
                old=existing.get(student)
                if old and _row_matches(old,incoming):
                    continue
                doc=frappe.get_doc('Student Attendance',old.name) if old else frappe.new_doc('Student Attendance')
                doc.student=student
                doc.attendance_session=session.name
                doc.status=incoming['status']
                doc.late_minutes=incoming['late_minutes']
                if 'remarks' in incoming:
                    doc.remarks=incoming['remarks']
                # Identity, scope and the exact roster have been authorized above.
                doc.save(ignore_permissions=True)
                if old: updated+=1
                else: created+=1
            session.reload()
            session.status='Completed'
            session.attendance_finalized=1
            session.save(ignore_permissions=True)
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        raise
    session.reload()
    response=_roster_response(session)
    response.update(created=created,updated=updated,idempotent=False)
    return response


def _pagination(limit_start,page_length):
    def integer(value):
        if isinstance(value,bool):
            frappe.throw(_('Invalid pagination.'))
        try:
            parsed=int(value)
            if str(parsed)!=str(value):
                raise ValueError
            return parsed
        except (TypeError,ValueError):
            frappe.throw(_('Pagination must use integers.'))
    start,size=integer(limit_start),integer(page_length)
    if start<0 or start>1_000_000 or not 1<=size<=200:
        frappe.throw(_('Pagination requires start >= 0 and page_length between 1 and 200.'))
    return start,size


@frappe.whitelist(methods=['GET'])
def get_advisor_dashboard(advisor_user=None,limit_start=0,page_length=50,academic_term=None,status='active'):
    from student_crm.experience import advisor_dashboard
    return advisor_dashboard(advisor_user,limit_start,page_length,academic_term,status)
