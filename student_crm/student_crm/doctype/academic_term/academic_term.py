from frappe.model.document import Document
import frappe
from student_crm.attendance import validate_dates

class AcademicTerm(Document):
    def validate(self):
        validate_dates(self)
        if self.is_current and frappe.db.exists('Academic Term',{'is_current':1,'name':['!=',self.name or '']}):
            frappe.throw('Another academic term is already marked current. Uncheck it first.')
