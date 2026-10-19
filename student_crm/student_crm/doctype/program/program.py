from frappe.model.document import Document
from student_crm.attendance import nonnegative

class Program(Document):
    def validate(self):
        nonnegative(self,'duration_years','total_required_credits')
