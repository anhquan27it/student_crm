from frappe.model.document import Document
import frappe
from frappe.utils import cint, getdate, get_time, today
from student_crm.attendance import check_duplicate, lock_offering, eligible, refresh_offering

class ClassSession(Document):
    def before_insert(self):
        if not self.session_id:
            from frappe.model.naming import make_autoname
            self.session_id=make_autoname('SES-.YYYY.-.#####')
            while frappe.db.exists(self.doctype,self.session_id):
                self.session_id=make_autoname('SES-.YYYY.-.#####')

    def validate(self):
        lock_offering(self.course_offering)
        check_duplicate(self,['course_offering','session_no'])
        if cint(self.session_no)<1 or not 1<=cint(self.slot_count)<=20:
            frappe.throw('Session number must be positive; slot count must be between 1 and 20.')
        if self.start_time and self.end_time and get_time(self.start_time)>=get_time(self.end_time):
            frappe.throw('End time must be after start time.')
        offering=frappe.get_doc('Course Offering',self.course_offering)
        if offering.start_date and getdate(self.session_date)<getdate(offering.start_date) or offering.end_date and getdate(self.session_date)>getdate(offering.end_date):
            frappe.throw('Session date must fall within the offering dates.')
        active=frappe.get_all('Class Session',filters={'course_offering':self.course_offering,'name':['!=',self.name or ''],'status':['not in',['Cancelled','Postponed']]},pluck='slot_count')
        if self.status not in ('Cancelled','Postponed') and sum(cint(n) for n in active)+cint(self.slot_count)>20:
            frappe.throw('Active sessions must not exceed 20 course slots.')
        if self.original_session:
            original=frappe.get_doc('Class Session',self.original_session)
            if self.original_session==self.name or original.course_offering!=self.course_offering or original.status not in ('Cancelled','Postponed'):
                frappe.throw('Original session must be a cancelled or postponed session of the same offering.')
        old=self.get_doc_before_save()
        if old and any(self.get(f)!=old.get(f) for f in ['course_offering','session_date','session_no','slot','slot_count','session_type','delivery_mode']):
            if frappe.db.exists('Student Attendance',{'attendance_session':self.name}):
                frappe.throw('Session details cannot change once attendance exists. Correct attendance first.')
        if self.attendance_finalized:
            from frappe.utils import now_datetime
            if self.status!='Completed' or getdate(self.session_date)>getdate(today()):
                frappe.throw('Only completed sessions that are not in the future can be finalized.')
            enrollments=frappe.get_all('Student Course Enrollment',filters={'course_offering':self.course_offering},fields=['name','student','status','enrollment_date','withdrawal_date'])
            students={e.student for e in enrollments if eligible(e,self.session_date)}
            records=frappe.get_all('Student Attendance',filters={'attendance_session':self.name},fields=['student','status'])
            if any(r.status not in ('Present','Absent','Late') for r in records):
                frappe.throw('Unsupported attendance status.')
            if not students or students!={r.student for r in records}:
                frappe.throw('Cannot finalize: attendance must exactly match eligible enrolled students. Fix missing enrollment/attendance first.')

            if not old or not old.attendance_finalized:
                self.attendance_recorded_by=frappe.session.user
                self.attendance_recorded_at=now_datetime()

    def on_update(self):
        refresh_offering(self.course_offering)

    def on_trash(self):
        lock_offering(self.course_offering)
        if self.attendance_finalized or frappe.db.exists('Student Attendance',{'attendance_session':self.name}):
            frappe.throw('A finalized session or a session with attendance cannot be deleted.')

    def after_delete(self):
        refresh_offering(self.course_offering)
