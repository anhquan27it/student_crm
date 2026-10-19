"""Install-time setup shared by fresh installs and subsequent migrations."""
import frappe


def after_install():
    ensure_setup()
    settings=frappe.get_single('CRM Settings')
    settings.flags.skip_rebuild=True
    settings.save(ignore_permissions=True)


def ensure_setup():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({
        **{dt:[dict(fieldname='support_case',label='Support Case',fieldtype='Link',
            options='Student Support Case',read_only=1,insert_after='student')]
            for dt in ['Student Warning','Intervention Log']},
        'Notification Log':[dict(fieldname='crm_event_key',label='CRM Event Key',fieldtype='Data',
            unique=1,hidden=1,read_only=1)],
    },ignore_validate=True)
    if not frappe.db.exists('Notification Type','Student CRM'):
        frappe.get_doc(dict(doctype='Notification Type',type_name='Student CRM',enabled=1)).insert(ignore_permissions=True)
    for dt,fields in [
        ('Student Course Enrollment',['student','course_offering']),
        ('Student Attendance',['student','attendance_session']),
        ('Class Session',['course_offering','session_no']),
    ]:
        frappe.db.add_unique(dt,fields)
    for dt,fields,name in [
        ('Student',['advisor','risk_standing'],'advisor_risk_standing'),
        ('Student Warning',['student','is_active','status'],'student_active_status'),
        ('Student Warning',['assigned_to','is_active','status'],'advisor_active_status'),
        ('Student Course Enrollment',['course_offering','status'],'offering_status'),
        ('Class Session',['course_offering','attendance_finalized','session_date'],'offering_finalized_date'),
        ('Student Attendance',['student','session_date'],'student_attendance_date'),
        ('Student Support Case',['owner_advisor','status'],'advisor_case_status'),
        ('Advisor Assignment',['student','effective_to'],'student_assignment_end'),
        ('Attendance Correction Request',['attendance','status'],'attendance_correction_status'),
    ]:
        frappe.db.add_index(dt,fields,name)
    frappe.clear_cache()
