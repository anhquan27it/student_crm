import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, now_datetime, today

class InterventionLog(Document):
    def validate(self):
        warning=frappe.get_doc('Student Warning',self.warning)
        from student_crm.portal import assert_warning_access
        assert_warning_access(warning)
        self.student=warning.student
        faculty=frappe.get_doc('Faculty Member',self.advisor)
        if faculty.status!='Active' or not faculty.is_advisor:
            frappe.throw('Choose an active advisor.')
        if 'System Manager' not in frappe.get_roles() and faculty.user!=frappe.session.user:
            frappe.throw('You may only record your own interventions.',frappe.PermissionError)
        if get_datetime(self.contacted_at)>now_datetime():
            frappe.throw('Contact time cannot be in the future.')
        if self.next_follow_up_date and getdate(self.next_follow_up_date)<getdate(self.contacted_at):
            frappe.throw('Follow-up date cannot precede contact date.')
        old=self.get_doc_before_save()
        if old and (self.warning!=old.warning or self.advisor!=old.advisor):
            frappe.throw('Warning and advisor cannot change on an existing intervention.')
        self.recorded_by=old.recorded_by if old else frappe.session.user
        self.recorded_at=old.recorded_at if old else now_datetime()

    def on_update(self):
        warning=frappe.get_doc('Student Warning',self.warning)
        # No automatic resolution: contacting a student does not remove exam ineligibility.
        if warning.status=='Open':
            warning.status='In Progress'
        if self.next_follow_up_date:
            warning.next_follow_up_date=self.next_follow_up_date
        warning.save(ignore_permissions=True)

    def on_trash(self):
        frappe.throw('Intervention logs are retained for audit.')
