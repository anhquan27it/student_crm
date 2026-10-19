"""Attendance rules: 20 slots per offering; warning strictly above 20%."""
import frappe
from frappe.utils import cint, flt, getdate, now_datetime

TOTAL_SLOTS = 20
THRESHOLD = 20
ABSENT_STATUSES = ('Absent',)

def eligible(enrollment, date):
    date = getdate(date)
    if enrollment.enrollment_date and date < getdate(enrollment.enrollment_date):
        return False
    if enrollment.status in ('Dropped', 'Withdrawn'):
        return bool(enrollment.withdrawal_date and date < getdate(enrollment.withdrawal_date))
    return True

def lock_offering(name):
    # Serialize saves that change aggregates or finalization in the same class.
    frappe.db.sql('select name from `tabCourse Offering` where name=%s for update', (name,))

def check_duplicate(doc, fields):
    filters = {f: doc.get(f) for f in fields}
    filters['name'] = ['!=', doc.name or '']
    if frappe.db.exists(doc.doctype, filters):
        frappe.throw('A record already exists for this combination: ' + ', '.join(fields))

def validate_dates(doc, start='start_date', end='end_date'):
    if doc.get(start) and doc.get(end) and getdate(doc.get(start)) > getdate(doc.get(end)):
        frappe.throw('Start date must not be after end date.')

def nonnegative(doc, *fields):
    for f in fields:
        if flt(doc.get(f)) < 0:
            frappe.throw(f + ' must not be negative.')

def attendance_values(doc):
    session = frappe.get_doc('Class Session', doc.attendance_session)
    offering = frappe.get_doc('Course Offering', session.course_offering)
    doc.student_name = frappe.db.get_value('Student', doc.student, 'student_name')
    doc.course_offering = offering.name
    doc.course = offering.course
    doc.academic_term = offering.academic_term
    doc.session_date = session.session_date
    doc.session_no = session.session_no
    doc.slot = session.slot
    doc.attendance_type = 'Make-up' if session.session_type == 'Make-up' else ('Online' if session.delivery_mode == 'Online' else 'Regular')
    doc.enrollment = frappe.db.get_value('Student Course Enrollment', {'student':doc.student,'course_offering':offering.name}, 'name')
    return session


from student_crm.attendance_service import schedule_refresh as refresh_offering, refresh_students

def refresh_enrollment(name):
    refresh_offering(frappe.db.get_value('Student Course Enrollment',name,'course_offering'))

def refresh_student(name):
    refresh_students([name])
