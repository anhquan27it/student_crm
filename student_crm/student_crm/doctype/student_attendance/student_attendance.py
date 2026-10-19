from frappe.model.document import Document
import frappe
from frappe.utils import cint, now_datetime
from student_crm.attendance import attendance_values, check_duplicate, lock_offering, eligible, refresh_offering

class StudentAttendance(Document):
    def before_insert(self):
        if not self.attendance_id:
            from frappe.model.naming import make_autoname
            self.attendance_id=make_autoname('ATT-.YYYY.-.#####')
            while frappe.db.exists(self.doctype,self.attendance_id):
                self.attendance_id=make_autoname('ATT-.YYYY.-.#####')

    def validate(self):
        session=attendance_values(self)
        lock_offering(self.course_offering)
        # Reload after acquiring the class lock to avoid racing finalization.
        session.reload()
        old=self.get_doc_before_save()
        if old and (self.student!=old.student or self.attendance_session!=old.attendance_session):
            frappe.throw('Student and session cannot change on an attendance record.')
        if session.attendance_finalized:
            frappe.throw('Uncheck Attendance Finalized on the session before correcting attendance.')
        if session.status in ('Cancelled','Postponed'):
            frappe.throw('Cannot record attendance for a cancelled or postponed session.')
        if not self.enrollment or not eligible(frappe.get_doc('Student Course Enrollment',self.enrollment),session.session_date):
            frappe.throw('Student needs an eligible enrollment for this session date.')
        check_duplicate(self,['student','attendance_session'])
        if cint(self.late_minutes)<0 or self.status!='Late' and cint(self.late_minutes):
            frappe.throw('Late minutes must be nonnegative and used only with Late status.')
        if self.status not in ('Present','Absent','Late'):
            frappe.throw('Only Present, Absent and Late are valid attendance statuses.')
        if self.is_new():
            self.recorded_by=frappe.session.user
            self.recorded_at=now_datetime()
        else:
            self.recorded_by=old.recorded_by or old.owner
            self.recorded_at=old.recorded_at or old.creation

    def on_update(self):
        refresh_offering(self.course_offering)

    def on_trash(self):
        lock_offering(self.course_offering)
        if frappe.db.get_value('Class Session',self.attendance_session,'attendance_finalized'):
            frappe.throw('Unfinalize the session before deleting attendance.')

    def after_delete(self):
        refresh_offering(self.course_offering)
