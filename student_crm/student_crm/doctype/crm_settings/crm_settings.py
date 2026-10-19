import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt

class CRMSettings(Document):
    def validate(self):
        if cint(self.default_total_sessions)!=20:
            frappe.throw('Each course must have 20 slots.')
        if not 0<flt(self.reminder_percentage)<flt(self.critical_percentage)<=flt(self.barred_percentage)<100:
            frappe.throw('Require 0 < reminder < critical <= barred < 100.')
        if not 7<=cint(self.behavioral_window_days)<=14 or cint(self.behavioral_consecutive_sessions)<2:
            frappe.throw('Behavioral window must be 7-14 days and consecutive session threshold >= 2.')
        if cint(self.near_limit_remaining)<0:
            frappe.throw('Near-limit remaining absences cannot be negative.')

    def on_update(self):
        # Recalculate derived data in the SAME transaction, including on rollback.
        # For very large deployments, replace with a versioned after-commit rebuild.
        if not self.flags.skip_rebuild:
            from student_crm.attendance_service import rebuild_all
            rebuild_all()
