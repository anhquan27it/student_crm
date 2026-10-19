from frappe.model.document import Document
import frappe
from student_crm.attendance import nonnegative

class Course(Document):
    def validate(self):
        nonnegative(self,'credits')
        if self.prerequisite and self.prerequisite == self.name:
            frappe.throw('A course cannot be its own prerequisite.')
