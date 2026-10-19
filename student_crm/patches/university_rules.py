import frappe
from student_crm.attendance_service import rebuild_all

def execute():
    settings=frappe.get_single('CRM Settings')
    settings.update(dict(default_total_sessions=20,reminder_percentage=10,critical_percentage=15,barred_percentage=20,
        near_limit_remaining=1,behavioral_consecutive_sessions=3,behavioral_window_days=14))
    settings.flags.skip_rebuild=True
    settings.save(ignore_permissions=True)
    # One Faculty Member per existing referenced User; do not create login accounts.
    users=set()
    for dt,field in [('Student','advisor'),('Course Offering','instructor'),('Class Session','instructor'),('Department','head_of_department'),('Student Warning','assigned_to')]:
        users.update(v for v in frappe.get_all(dt,pluck=field) if v)
    for user in sorted(users):
        if not frappe.db.exists('Faculty Member',user):
            u=frappe.db.get_value('User',user,['full_name','enabled'],as_dict=True)
            if not u:frappe.throw('Unresolved faculty User reference: '+user)
            frappe.get_doc(dict(doctype='Faculty Member',user=user,full_name=u.full_name,is_advisor=1,is_instructor=1,
                status='Active' if u.enabled else 'Inactive')).insert(ignore_permissions=True)
    # Preserve any old excuse text as historical notes; there is no excused status.
    for row in frappe.get_all('Student Attendance',filters={'status':'Excused'},fields=['name','remarks','excuse_reason']):
        notes='\n'.join(x for x in [row.remarks,'Legacy Excused converted to Absent.',row.excuse_reason] if x)
        frappe.db.set_value('Student Attendance',row.name,dict(status='Absent',remarks=notes),update_modified=False)
    # Old one-warning-per-enrollment key must no longer prevent severity history.
    indexes=frappe.db.sql('show index from `tabStudent Warning` where Key_name=%s',('enrollment',))
    if indexes:
        frappe.db.commit()
        frappe.db.sql('alter table `tabStudent Warning` drop index `enrollment`')
    frappe.db.add_index('Student Warning',['assigned_to','is_active','status'],'advisor_active_status')
    frappe.db.add_index('Student Course Enrollment',['course_offering','status'],'offering_status')
    frappe.db.add_index('Class Session',['course_offering','attendance_finalized','session_date'],'offering_finalized_date')
    frappe.db.add_index('Student Attendance',['student','session_date'],'student_attendance_date')
    rebuild_all()
