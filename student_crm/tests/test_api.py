"""API integration/security tests; no fixture data is committed."""
from pathlib import Path
import json
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days,today
from student_crm import api
from student_crm.tests.test_attendance_rules import UniversityAttendanceTests as Fixtures


class StudentCRMApiTests(unittest.TestCase):
    create=Fixtures.create
    offering_for=Fixtures.offering_for
    enroll=Fixtures.enroll
    session=Fixtures.session
    record=Fixtures.record
    finalize=Fixtures.finalize

    def setUp(self):
        frappe.set_user('Administrator')
        Fixtures.setUp(self)
        self.instructor=self.faculty('teacher',True,False)
        self.other_instructor=self.faculty('other-teacher',True,False)
        self.advisor=self.faculty('advisor',False,True)
        self.other_advisor=self.faculty('other-advisor',False,True)
        self.offering.instructor=self.instructor.name;self.offering.save(ignore_permissions=True)
        self.student.advisor=self.advisor.name;self.student.save(ignore_permissions=True)
        email=self.prefix.lower()+'-student@example.com'
        self.create('User',email=email,first_name='API student',enabled=1,user_type='Website User',send_welcome_email=0)
        self.student.user=email;self.student.save(ignore_permissions=True)
        self.student_user=email

    def tearDown(self):
        frappe.set_user('Administrator')
        Fixtures.tearDown(self)

    def faculty(self,label,instructor,advisor):
        user=self.prefix.lower()+'-'+label+'@example.com'
        self.create('User',email=user,first_name='API '+label,enabled=1,user_type='Website User',send_welcome_email=0)
        return self.create('Faculty Member',user=user,full_name='API '+label,is_instructor=int(instructor),is_advisor=int(advisor),status='Active')

    def data(self,status='Present',**kw):
        return [dict(student=self.student.name,status=status,**kw)]

    def test_roster_instructor_and_cached_metrics(self):
        s=self.session(instructor=self.instructor.name)
        frappe.set_user(self.instructor.user)
        response=api.get_session_roster(s.name)
        self.assertEqual(response['count'],1)
        self.assertEqual(response['students'][0]['absent_count'],0)
        self.assertEqual(response['students'][0]['remaining_absences'],4)
        self.assertIsNone(response['students'][0]['status'])
        self.assertTrue(response['session']['modified'])

    def test_guest_student_other_teacher_denied(self):
        s=self.session(instructor=self.instructor.name)
        for user in ['Guest',self.student_user,self.other_instructor.user,self.advisor.user]:
            frappe.set_user(user)
            with self.assertRaises(frappe.PermissionError):api.get_session_roster(s.name)
            with self.assertRaises(frappe.PermissionError):api.submit_bulk_attendance(s.name,self.data())

    def test_session_teacher_overrides_offering_teacher(self):
        s=self.session(instructor=self.other_instructor.name)
        frappe.set_user(self.instructor.user)
        with self.assertRaises(frappe.PermissionError):api.get_session_roster(s.name)
        frappe.set_user(self.other_instructor.user)
        self.assertEqual(api.get_session_roster(s.name)['count'],1)

    def test_bulk_finalizes_metrics_and_idempotent_retry(self):
        s=self.session(slots=5,instructor=self.instructor.name)
        frappe.set_user(self.instructor.user)
        version=api.get_session_roster(s.name)['session']['modified']
        response=api.submit_bulk_attendance(s.name,json.dumps(self.data('Absent')),version)
        self.assertEqual(response['created'],1)
        self.assertEqual(response['session']['attendance_finalized'],1)
        self.assertEqual(response['students'][0]['attendance_standing'],'Barred')
        self.assertEqual(response['students'][0]['absent_count'],5)
        self.assertEqual(frappe.db.get_value('Class Session',s.name,'attendance_recorded_by'),self.instructor.user)
        retry=api.submit_bulk_attendance(s.name,self.data('Absent'),version)
        self.assertTrue(retry['idempotent'])
        self.assertEqual(retry['created'],0)
        self.assertEqual(retry['session']['modified'],response['session']['modified'])
        self.assertEqual(frappe.db.count('Student Attendance',{'attendance_session':s.name}),1)

    def test_correction_requires_version_and_resolves_warning(self):
        s=self.session(slots=5,instructor=self.instructor.name)
        frappe.set_user(self.instructor.user)
        first=api.submit_bulk_attendance(s.name,self.data('Absent'))
        with self.assertRaises(frappe.TimestampMismatchError):api.submit_bulk_attendance(s.name,self.data())
        with self.assertRaises(frappe.TimestampMismatchError):api.submit_bulk_attendance(s.name,self.data(),'2000-01-01 00:00:00')
        response=api.submit_bulk_attendance(s.name,self.data(),first['session']['modified'])
        self.assertEqual(response['updated'],1)
        self.assertEqual(response['students'][0]['attendance_standing'],'Good')
        self.assertEqual(frappe.db.count('Student Warning',{'student':self.student.name,'is_active':1}),0)

    def test_input_validation_happens_before_writes(self):
        s=self.session(instructor=self.instructor.name)
        frappe.set_user(self.instructor.user)
        bad=[self.data('Excused'),self.data('Late',late_minutes=-1),self.data('Late',late_minutes=True),
            self.data('Late',late_minutes='10'),self.data('Present',late_minutes=10),
            self.data('Present',course_offering='injected'),self.data()*2,[],{},'not json',
            self.data('Present',remarks=123)]
        for payload in bad:
            with self.assertRaises(frappe.ValidationError):api.submit_bulk_attendance(s.name,payload)
        large=[dict(student='S'+str(i),status='Present',remarks='x'*2000) for i in range(600)]
        with self.assertRaises(frappe.ValidationError):api.submit_bulk_attendance(s.name,large)
        self.assertEqual(frappe.db.count('Student Attendance',{'attendance_session':s.name}),0)
        self.assertEqual(frappe.db.get_value('Class Session',s.name,'attendance_finalized'),0)

    def test_exact_roster_and_unenrolled_student(self):
        other=self.create('Student',id_student=self.prefix+'-2',student_name='Second',program=self.program.name,admission_term=self.term.name,email='second@example.com',student_status='Active')
        self.enroll(self.offering,other.name)
        s=self.session(instructor=self.instructor.name)
        frappe.set_user(self.instructor.user)
        with self.assertRaises(frappe.ValidationError):api.submit_bulk_attendance(s.name,self.data())
        with self.assertRaises(frappe.ValidationError):api.submit_bulk_attendance(s.name,self.data()+[dict(student='unknown',status='Present')])
        response=api.submit_bulk_attendance(s.name,self.data()+[dict(student=other.name,status='Late',late_minutes=3)])
        self.assertEqual(response['created'],2)

    def test_atomic_rollback_on_mid_batch_error(self):
        other=self.create('Student',id_student=self.prefix+'-2',student_name='Second',program=self.program.name,admission_term=self.term.name,email='second@example.com',student_status='Active')
        self.enroll(self.offering,other.name)
        s=self.session(instructor=self.instructor.name)
        from student_crm.student_crm.doctype.student_attendance.student_attendance import StudentAttendance
        original=StudentAttendance.validate
        def fail_second(doc):
            if doc.student==other.name:raise frappe.ValidationError('Simulated failure')
            return original(doc)
        frappe.set_user(self.instructor.user)
        with patch.object(StudentAttendance,'validate',fail_second):
            with self.assertRaises(frappe.ValidationError):
                api.submit_bulk_attendance(s.name,self.data()+[dict(student=other.name,status='Present')])
        self.assertEqual(frappe.db.count('Student Attendance',{'attendance_session':s.name}),0)
        self.assertEqual(frappe.db.get_value('Class Session',s.name,'attendance_finalized'),0)
        self.enrollment.reload();self.assertEqual(self.enrollment.absent_count,0)

    def test_cancelled_future_disabled_profile(self):
        s=self.session(instructor=self.instructor.name,status='Cancelled')
        frappe.set_user(self.instructor.user)
        with self.assertRaises(frappe.ValidationError):api.submit_bulk_attendance(s.name,self.data())
        frappe.set_user('Administrator')
        future=self.session(2,instructor=self.instructor.name,days=1)
        frappe.set_user(self.instructor.user)
        with self.assertRaises(frappe.ValidationError):api.submit_bulk_attendance(future.name,self.data())
        frappe.set_user('Administrator');frappe.db.set_value('Faculty Member',self.instructor.name,'status','Inactive')
        frappe.set_user(self.instructor.user)
        with self.assertRaises(frappe.PermissionError):api.get_session_roster(future.name)

    def test_advisor_scope_and_high_risk(self):
        s=self.session(slots=5,instructor=self.instructor.name)
        api.submit_bulk_attendance(s.name,self.data('Absent'))
        frappe.set_user(self.advisor.user)
        response=api.get_advisor_dashboard()
        self.assertEqual(response['summary']['students']['total_students'],1)
        self.assertEqual(response['summary']['warnings']['barred'],1)
        self.assertEqual(response['high_risk_students'][0]['student'],self.student.name)
        self.assertEqual(response['warnings'][0]['severity'],'Barred')
        with self.assertRaises(frappe.PermissionError):api.get_advisor_dashboard(self.other_advisor.user)
        frappe.set_user(self.other_advisor.user)
        response=api.get_advisor_dashboard()
        self.assertEqual(response['warnings'],[])
        self.assertEqual(response['high_risk_students'],[])
        self.assertEqual(response['summary']['students']['total_students'],0)

    def test_dashboard_student_denial_admin_and_pagination(self):
        frappe.set_user(self.student_user)
        self.assertFalse(frappe.has_permission('Student',ptype='read',user=self.student_user))
        with self.assertRaises(frappe.PermissionError):api.get_advisor_dashboard()
        frappe.set_user(self.instructor.user)
        with self.assertRaises(frappe.PermissionError):api.get_advisor_dashboard()
        frappe.set_user('Administrator')
        response=api.get_advisor_dashboard(self.advisor.user,page_length='1',limit_start='0')
        self.assertEqual(response['scope'],'advisor')
        self.assertEqual(response['summary']['students']['total_students'],1)
        self.assertEqual(api.get_advisor_dashboard()['scope'],'all')
        for start,size in [(-1,50),(0,201),(0,0),(0,True),(0,'1.5')]:
            with self.assertRaises(frappe.ValidationError):api.get_advisor_dashboard(limit_start=start,page_length=size)

    def test_http_method_registration(self):
        self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[api.get_session_roster],['GET'])
        self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[api.submit_bulk_attendance],['POST'])
        self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[api.get_advisor_dashboard],['GET'])
        self.assertNotIn(api.submit_bulk_attendance,frappe.guest_methods)


if __name__=='__main__':
    frappe.init(site='studentcrm.local');frappe.connect();frappe.set_user('Administrator')
    try:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StudentCRMApiTests))
    finally:
        frappe.db.rollback();frappe.destroy()
    raise SystemExit(0 if result.wasSuccessful() else 1)
