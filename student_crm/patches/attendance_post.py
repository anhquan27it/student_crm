import frappe
from frappe.model.utils.rename_field import rename_field
from student_crm.attendance import attendance_values, refresh_offering

def execute():
    # A fresh schema already uses the corrected field names. Never reset its attendance.
    if not any(frappe.db.has_column(dt,field) for dt,field in
               [('Student','adresss'),('Class Session','sesion_no'),('Academic Term','start')]):
        return
    for dt, old, new in [('Student','adresss','address'),('Student','registerd_credits','registered_credits'),('Academic Term','start','start_date'),('Class Session','sesion_no','session_no'),('Class Session','instuctor','instructor')]:
        rename_field(dt,old,new)
    frappe.db.sql("update `tabCourse` set course_type='Compulsory' where ifnull(course_type,'')='' ")
    frappe.db.sql("update `tabClass Session` set session_type=case when status='Make-up' then 'Make-up' else 'Regular' end, status=case when status='Make-up' then 'Scheduled' else status end, slot_count=1, attendance_finalized=0, delivery_mode='Offline'")
    frappe.db.sql('update `tabCourse Offering` set total_slots=20, warning_threshold=20, planned_hours=20*ifnull(hours_per_slot,0)')
    for dt,cols in [('Student Course Enrollment',['student','course_offering']),('Student Attendance',['student','attendance_session']),('Class Session',['course_offering','session_no'])]:
        frappe.db.add_unique(dt,cols)
    for row in frappe.get_all('Student Course Enrollment',fields=['name','student','course_offering']):
        offering=frappe.get_doc('Course Offering',row.course_offering)
        frappe.db.set_value('Student Course Enrollment',row.name,dict(student_name=frappe.db.get_value('Student',row.student,'student_name'),course=offering.course,academic_term=offering.academic_term,credit=frappe.db.get_value('Course',offering.course,'credits')),update_modified=False)
    for row in frappe.get_all('Student Attendance',pluck='name'):
        doc=frappe.get_doc('Student Attendance',row)
        attendance_values(doc)
        values={f:doc.get(f) for f in ['student_name','course_offering','course','academic_term','session_date','session_no','slot','attendance_type','enrollment']}
        values.update(recorded_by=doc.recorded_by or doc.owner,recorded_at=doc.recorded_at or doc.creation)
        frappe.db.set_value('Student Attendance',row,values,update_modified=False)
    for name in frappe.get_all('Course Offering',pluck='name'):
        refresh_offering(name)
