import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class StudentWarning(Document):
    def validate(self):
        if self.warning_type=='Course-Level' and (not self.enrollment or not self.course_offering):
            frappe.throw('Course-level warnings require enrollment and offering.')
        if self.warning_type=='Behavioral-Level' and (self.enrollment or self.course_offering):
            frappe.throw('Behavioral warnings span courses; enrollment and offering must be blank.')
        if not self.flags.automatic_warning:
            old=self.get_doc_before_save()
            editable={'status','assigned_to','follow_up_notes','next_follow_up_date'}
            protected=[f.fieldname for f in self.meta.fields if f.fieldtype not in ('Section Break','Column Break','Tab Break') and f.fieldname not in editable]
            if not old or any(str(self.get(f) or '')!=str(old.get(f) or '') for f in protected):
                frappe.throw('Warning metrics are maintained by the attendance service.')
            if self.status=='Resolved' and old.status!='Resolved':
                self.resolved_at=now_datetime()

    def on_trash(self):
        frappe.throw('Keep warning history. Resolve the warning instead of deleting it.')
