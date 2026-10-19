from frappe.model.document import Document
import frappe
from student_crm.attendance import check_duplicate, lock_offering, validate_dates, refresh_offering, refresh_student

class StudentCourseEnrollment(Document):
    def before_insert(self):
        if not self.enrollment_id:
            from frappe.model.naming import make_autoname
            self.enrollment_id=make_autoname('ENR-.YYYY.-.#####')
            while frappe.db.exists(self.doctype,self.enrollment_id):
                self.enrollment_id=make_autoname('ENR-.YYYY.-.#####')

    def validate(self):
        lock_offering(self.course_offering)
        check_duplicate(self,['student','course_offering'])
        old=self.get_doc_before_save()
        if old and (self.student != old.student or self.course_offering != old.course_offering):
            frappe.throw('Student and class cannot change on an existing enrollment; create a new enrollment.')
        offering=frappe.get_doc('Course Offering',self.course_offering)
        self.student_name=frappe.db.get_value('Student',self.student,'student_name')
        self.course=offering.course
        self.academic_term=offering.academic_term
        self.credit=frappe.db.get_value('Course',offering.course,'credits')
        if self.status in ('Dropped','Withdrawn') and not self.withdrawal_date:
            frappe.throw('Withdrawal date is required for a dropped or withdrawn enrollment.')
        validate_dates(self,'enrollment_date','withdrawal_date')
        if old and any(self.get(f)!=old.get(f) for f in ['enrollment_date','withdrawal_date','status']):
            if frappe.db.exists('Class Session',{'course_offering':self.course_offering,'attendance_finalized':1}):
                frappe.throw('Unfinalize class attendance before changing enrollment eligibility.')
        if offering.capacity and self.status=='Enrolled':
            count=frappe.db.count('Student Course Enrollment',{'course_offering':offering.name,'status':'Enrolled','name':['!=',self.name or '']})
            if count>=offering.capacity:
                frappe.throw('Class capacity has been reached.')
        if self.is_new() and frappe.db.exists('Class Session',{'course_offering':self.course_offering,'attendance_finalized':1}):
            from student_crm.attendance import eligible
            for s in frappe.get_all('Class Session',filters={'course_offering':self.course_offering,'attendance_finalized':1},fields=['session_date']):
                if eligible(self,s.session_date):
                    frappe.throw('Unfinalize affected sessions before adding a retroactive enrollment.')

    def on_update(self):
        refresh_offering(self.course_offering)

    def on_trash(self):
        if frappe.db.exists('Student Attendance',{'student':self.student,'course_offering':self.course_offering}) or frappe.db.exists('Student Warning',{'enrollment':self.name}):
            frappe.throw('Keep enrollment history; use a withdrawal status instead of deleting.')

    def after_delete(self):
        refresh_student(self.student)
