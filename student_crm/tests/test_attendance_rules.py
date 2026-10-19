"""Integration tests with transaction rollback against the development site."""
import json
import unittest
import uuid
import frappe
from frappe.utils import add_days, today, now_datetime
from student_crm.attendance_service import refresh_students, defer_refresh


class UniversityAttendanceTests(unittest.TestCase):
    def setUp(self):
        frappe.db.savepoint('crm_university_test')
        self.prefix='QA-'+uuid.uuid4().hex[:10]
        self.department=self.create('Department',department_code=self.prefix,department_name=self.prefix,status='Active')
        self.program=self.create('Program',program_code=self.prefix,program_name=self.prefix,department=self.department.name)
        self.term=self.create('Academic Term',term_code=self.prefix,term_name=self.prefix,academic_year='2026-2027',start_date=add_days(today(),-60),end_date=add_days(today(),60),status='In Progress')
        self.course=self.create('Course',course_code=self.prefix,course_name='University rules test',department=self.department.name,credits=3,course_type='Compulsory',status='Active')
        self.student=self.create('Student',id_student=self.prefix,student_name='Test',program=self.program.name,admission_term=self.term.name,email=self.prefix+'@example.com',student_status='Active')
        self.offering=self.offering_for('1')
        self.enrollment=self.enroll(self.offering)

    def tearDown(self):
        frappe.db.rollback(save_point='crm_university_test')
        frappe.clear_messages()

    def create(self,dt,**kw):
        return frappe.get_doc(dict(doctype=dt,**kw)).insert(ignore_permissions=True)

    def offering_for(self,suffix):
        return self.create('Course Offering',offering_code=self.prefix+'-'+suffix,course=self.course.name,academic_term=self.term.name,status='In Progress',total_slots=99)

    def enroll(self,offering,student=None):
        return self.create('Student Course Enrollment',student=student or self.student.name,course_offering=offering.name,enrollment_date=add_days(today(),-30),status='Enrolled')

    def session(self,number=1,slots=1,offering=None,days=-20,**kw):
        values=dict(course_offering=(offering or self.offering).name,session_no=number,slot_count=slots,session_date=add_days(today(),days),status='Completed')
        values.update(kw)
        return self.create('Class Session',**values)

    def record(self,session,status='Absent',**kw):
        values=dict(student=self.student.name,attendance_session=session.name,status=status)
        values.update(kw)
        return self.create('Student Attendance',**values)

    def finalize(self,session):
        session.reload();session.attendance_finalized=1;session.save(ignore_permissions=True)

    def active(self,kind=None):
        filters={'student':self.student.name,'is_active':1}
        if kind:filters['warning_type']=kind
        return frappe.get_all('Student Warning',filters=filters,fields=['name','severity','warning_type'])

    def test_course_threshold_and_correction(self):
        for n in range(1,5):
            s=self.session(n);self.record(s);self.finalize(s)
        self.enrollment.reload()
        self.assertEqual(self.enrollment.absent_count,4)
        self.assertEqual(self.enrollment.absent_percentage,20)
        self.assertEqual(self.enrollment.remaining_absences,0)
        self.assertEqual(self.enrollment.attendance_standing,'Critical')
        self.assertEqual([x.severity for x in self.active('Course-Level')],['Critical'])
        s=self.session(5);a=self.record(s);self.finalize(s)
        self.enrollment.reload()
        self.assertEqual(self.enrollment.attendance_standing,'Barred')
        self.assertEqual(self.enrollment.absent_percentage,25)
        barred=frappe.get_doc('Student Warning',self.active('Course-Level')[0].name)
        self.assertEqual(barred.severity,'Barred')
        barred.follow_up_notes='Preserve intervention history';barred.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            a.reload();a.status='Present';a.save(ignore_permissions=True)
        s.reload();s.attendance_finalized=0;s.save(ignore_permissions=True)
        a.reload();a.status='Present';a.save(ignore_permissions=True);self.finalize(s)
        self.enrollment.reload();barred.reload()
        self.assertEqual(self.enrollment.attendance_standing,'Critical')
        self.assertEqual(barred.is_active,0)
        s.reload();s.attendance_finalized=0;s.save(ignore_permissions=True)
        a.reload();a.status='Absent';a.save(ignore_permissions=True);self.finalize(s)
        barred.reload()
        self.assertEqual(barred.is_active,1)
        self.assertEqual(barred.occurrence_count,2)
        self.assertEqual(barred.follow_up_notes,'Preserve intervention history')
        self.assertEqual(frappe.db.count('Student Warning',{'enrollment':self.enrollment.name,'severity':'Barred'}),1)

    def test_near_limit_and_threshold_settings(self):
        settings=frappe.get_single('CRM Settings')
        settings.critical_percentage=20;settings.save(ignore_permissions=True)
        s=self.session(1,slots=3);self.record(s);self.finalize(s)
        self.enrollment.reload()
        self.assertEqual(self.enrollment.remaining_absences,1)
        self.assertEqual(self.enrollment.attendance_standing,'Critical')
        settings.barred_percentage=10;settings.critical_percentage=10
        settings.reminder_percentage=5;settings.save(ignore_permissions=True)
        self.enrollment.reload()
        self.assertEqual(self.enrollment.attendance_standing,'Barred')

    def test_cross_course_behavioral_and_expiry(self):
        other=self.offering_for('2');self.enroll(other)
        for n in range(1,4):
            s=self.session(n,offering=other if n==2 else self.offering,days=n-4)
            self.record(s);self.finalize(s)
        warnings=self.active('Behavioral-Level')
        self.assertEqual(len(warnings),1)
        w=frappe.get_doc('Student Warning',warnings[0].name)
        self.assertEqual(w.consecutive_sessions,3)
        self.assertFalse(w.course_offering)
        self.assertEqual(len(json.loads(w.evidence_json)),3)
        self.student.reload();self.assertEqual(self.student.risk_standing,'Critical')
        refresh_students([self.student.name],as_of=add_days(today(),15))
        w.reload();self.assertEqual(w.is_active,0)
        self.assertEqual(w.status,'Resolved')

    def test_present_and_late_break_behavioral_streak(self):
        for n,status in enumerate(['Absent','Late','Absent','Present','Absent'],1):
            s=self.session(n,days=n-6);self.record(s,status);self.finalize(s)
        self.student.reload()
        self.assertEqual(self.student.behavioral_absence_streak,1)
        self.assertEqual(self.active('Behavioral-Level'),[])
        self.enrollment.reload();self.assertEqual(self.enrollment.absent_count,3)

    def test_missing_record_not_inferred_as_absent(self):
        for n in range(1,3):
            s=self.session(n,days=n-4);self.record(s);self.finalize(s)
        s=self.session(3,days=-1)
        with self.assertRaises(frappe.ValidationError):self.finalize(s)
        # Simulate a legacy incomplete finalized session without invoking hooks.
        frappe.db.set_value('Class Session',s.name,'attendance_finalized',1)
        refresh_students([self.student.name])
        self.student.reload();self.assertEqual(self.student.behavioral_absence_streak,0)
        self.assertEqual(self.active('Behavioral-Level'),[])

    def test_status_duplicates_and_enrollment_validation(self):
        s=self.session()
        with self.assertRaises(frappe.ValidationError):self.record(s,'Excused')
        self.record(s)
        with self.assertRaises(frappe.ValidationError):self.record(s)
        with self.assertRaises(frappe.ValidationError):self.session()
        with self.assertRaises(frappe.ValidationError):self.enroll(self.offering)
        other=self.create('Student',id_student=self.prefix+'-2',student_name='Unenrolled',program=self.program.name,admission_term=self.term.name,email='qa2@example.com',student_status='Active')
        with self.assertRaises(frappe.ValidationError):self.record(s,student=other.name)

    def test_multislot_bulk_and_unfinalized(self):
        with defer_refresh():
            s=self.session(slots=4);self.record(s)
            self.enrollment.reload();self.assertEqual(self.enrollment.absent_count,0)
            self.finalize(s)
            s2=self.session(2,slots=2);self.record(s2,'Late',late_minutes=10);self.finalize(s2)
        self.enrollment.reload()
        self.assertEqual(self.enrollment.absent_count,4)
        self.assertEqual(self.enrollment.late_count,2)
        self.assertEqual(self.enrollment.completed_sessions,6)
        self.assertEqual(self.enrollment.total_sessions,20)
        self.assertEqual(self.enrollment.attendance_standing,'Critical')

    def test_intervention_and_warning_protection(self):
        s=self.session(slots=2);self.record(s);self.finalize(s)
        warning=frappe.get_doc('Student Warning',self.active('Course-Level')[0].name)
        faculty=frappe.db.get_value('Faculty Member',{'user':'Administrator'},'name')
        if not faculty:
            faculty=self.create('Faculty Member',user='Administrator',full_name='Administrator',is_advisor=1).name
        else:
            frappe.db.set_value('Faculty Member',faculty,'is_advisor',1)
        log=self.create('Intervention Log',warning=warning.name,advisor=faculty,contacted_at=now_datetime(),channel='Phone',contact_result='Reached',summary='Discussed attendance',outcome='Monitoring')
        self.assertEqual(log.student,self.student.name)
        self.assertEqual(log.recorded_by,'Administrator')
        warning.reload();self.assertEqual(warning.status,'In Progress')
        warning.absent_slots=999
        with self.assertRaises(frappe.ValidationError):warning.save(ignore_permissions=True)

    def test_cancelled_future_and_slot_limit(self):
        self.offering.reload();self.assertEqual(self.offering.total_slots,20)
        s=self.session(slots=20)
        with self.assertRaises(frappe.ValidationError):self.session(2)
        s.status='Cancelled';s.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):self.record(s)
        s2=self.session(3,days=1);self.record(s2)
        with self.assertRaises(frappe.ValidationError):self.finalize(s2)

    def test_invalid_settings(self):
        settings=frappe.get_single('CRM Settings');settings.behavioral_window_days=30
        with self.assertRaises(frappe.ValidationError):settings.save(ignore_permissions=True)
        settings.behavioral_window_days=14;settings.reminder_percentage=30
        with self.assertRaises(frappe.ValidationError):settings.save(ignore_permissions=True)

    def test_daily_job_clears_expired_partial_streak(self):
        from student_crm.attendance_service import expire_behavioral_warnings
        sessions=[]
        for n in range(1,3):
            s=self.session(n,days=n-3);self.record(s);self.finalize(s);sessions.append(s)
        self.student.reload();self.assertEqual(self.student.behavioral_absence_streak,2)
        self.assertEqual(self.active('Behavioral-Level'),[])
        # Move fixtures outside the window without changing production clock.
        for s in sessions:
            frappe.db.set_value('Class Session',s.name,'session_date',add_days(today(),-20))
        expire_behavioral_warnings()
        self.student.reload();self.assertEqual(self.student.behavioral_absence_streak,0)


if __name__=='__main__':
    frappe.init(site='studentcrm.local');frappe.connect();frappe.set_user('Administrator')
    try:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UniversityAttendanceTests))
    finally:
        frappe.db.rollback();frappe.destroy()
    raise SystemExit(0 if result.wasSuccessful() else 1)
