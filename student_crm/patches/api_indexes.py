import frappe

def execute():
    frappe.db.add_index('Student',['advisor','risk_standing'],'advisor_risk_standing')
    frappe.db.add_index('Student Warning',['student','is_active','status'],'student_active_status')
