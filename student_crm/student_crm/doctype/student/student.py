from frappe.model.document import Document
import frappe
from frappe.utils import getdate, today
from student_crm.attendance import validate_dates

class Student(Document):
    def validate(self):
        self.department=frappe.db.get_value('Program',self.program,'department')
        validate_dates(self,'enrollment_date','expected_graduation_date')
        if self.date_of_birth and getdate(self.date_of_birth) > getdate(today()):
            frappe.throw('Date of birth cannot be in the future.')
