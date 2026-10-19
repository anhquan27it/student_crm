from frappe.model.document import Document
import frappe
from frappe.utils import flt
from student_crm.attendance import nonnegative, validate_dates

class CourseOffering(Document):
    def validate(self):
        self.total_slots=20
        from student_crm.attendance_service import get_policy
        self.warning_threshold=float(get_policy().barred)
        self.planned_hours=20*flt(self.hours_per_slot)
        nonnegative(self,'capacity','hours_per_slot')
        validate_dates(self)
        old=self.get_doc_before_save()
        if old and any(self.get(f)!=old.get(f) for f in ['course','academic_term']):
            if frappe.db.exists('Class Session',{'course_offering':self.name}) or frappe.db.exists('Student Course Enrollment',{'course_offering':self.name}):
                frappe.throw('Course and term cannot change after sessions or enrollments exist.')
