from frappe.model.document import Document
from student_crm import support

class StudentSupportCase(Document):
    def validate(self):
        support.validate_document(self)
    def on_trash(self):
        support.prevent_delete(self)
