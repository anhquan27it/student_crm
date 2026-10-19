import frappe

def execute():
    if not frappe.db.exists('DocType','Student'):
        return
    if frappe.get_meta("Student").get_field("date_of_birth").fieldtype != "Int":
        return
    # Old date_of_birth contains years, not dates. Preserve before changing SQL type.
    if not frappe.db.has_column('Student','birth_year'):
        frappe.db.sql('alter table `tabStudent` add column `birth_year` int')
    frappe.db.sql('update `tabStudent` set birth_year=date_of_birth where date_of_birth between 1900 and 2100')
    frappe.db.commit()
    frappe.db.sql('alter table `tabStudent` modify column `date_of_birth` int NULL')
    frappe.db.sql('update `tabStudent` set date_of_birth=NULL')
    # Validate that data allows unique constraints before schema changes.
    for dt, cols in [('Student Course Enrollment',['student','course_offering']),('Student Attendance',['student','attendance_session']),('Class Session',['course_offering','sesion_no'])]:
        group=', '.join('`'+c+'`' for c in cols)
        if frappe.db.sql('select count(*) from `tab'+dt+'` group by '+group+' having count(*)>1 limit 1'):
            frappe.throw('Duplicate records must be resolved before migration: '+dt)
