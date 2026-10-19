import frappe
from frappe.model.document import Document

class FacultyMember(Document):
    def validate(self):
        user=frappe.db.get_value('User',self.user,['full_name','email','enabled'],as_dict=True)
        if not user or self.status=='Active' and not user.enabled:
            frappe.throw('An active faculty member requires an enabled User.')
        self.full_name=self.full_name or user.full_name
        self.email=user.email
        old=self.get_doc_before_save()
        if old and self.user!=old.user:
            frappe.throw('User cannot be changed on an existing faculty member.')
