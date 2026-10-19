import unittest
from unittest.mock import patch
import frappe
from student_crm import portal,api
from student_crm.tests.test_api import StudentCRMApiTests as F

class PortalTests(unittest.TestCase):
    create=F.create;offering_for=F.offering_for;enroll=F.enroll;session=F.session;record=F.record;finalize=F.finalize
    faculty=F.faculty;data=F.data;setUp=F.setUp;tearDown=F.tearDown

    def test_student_directory_counts_and_filters_across_pages(self):
        second=self.create('Student',id_student=self.prefix+'-PAGE2',student_name='Second directory student',
            program=self.program.name,admission_term=self.term.name,email='directory@example.com',
            student_status='Active',advisor=self.advisor.name)
        frappe.db.set_value('Student',second.name,'risk_standing','Barred')
        frappe.set_user(self.advisor.user)
        first=portal.list_students(page_length=1)
        following=portal.list_students(limit_start=1,page_length=1)
        self.assertEqual(first['total_count'],2);self.assertTrue(first['has_more'])
        self.assertTrue(first['scoped_to_advisor'])
        self.assertNotEqual(first['items'][0].name,following['items'][0].name)
        filtered=portal.list_students(risk_standing='Barred',page_length=1)
        self.assertEqual(filtered['total_count'],1)
        self.assertEqual(filtered['items'][0].name,second.name)
        self.assertEqual(portal.list_students(search=second.name)['total_count'],1)
        with self.assertRaises(frappe.ValidationError):portal.list_students(risk_standing='invalid')

    def test_advisor_scopes_lists_and_details(self):
        s=self.session(slots=5,instructor=self.instructor.name);api.submit_bulk_attendance(s.name,self.data('Absent'))
        warning=frappe.db.get_value('Student Warning',{'student':self.student.name,'is_active':1},'name')
        frappe.set_user(self.advisor.user)
        self.assertEqual(portal.list_students()['items'][0].name,self.student.name)
        self.assertTrue(portal.get_student_detail(self.student.name)['can_advise'])
        self.assertEqual(portal.get_warning_detail(warning)['warning']['student'],self.student.name)
        frappe.set_user(self.other_advisor.user)
        self.assertEqual(portal.list_students()['items'],[])
        with self.assertRaises(frappe.PermissionError):portal.get_student_detail(self.student.name)
        with self.assertRaises(frappe.PermissionError):portal.get_warning_detail(warning)

    def test_advisor_can_record_intervention_through_controller(self):
        s=self.session(slots=5,instructor=self.instructor.name);api.submit_bulk_attendance(s.name,self.data('Absent'))
        warning=frappe.db.get_value('Student Warning',{'student':self.student.name,'is_active':1},'name')
        frappe.set_user(self.advisor.user)
        result=portal.save_intervention(warning,'Đã trao đổi và thống nhất kế hoạch hỗ trợ.')
        self.assertTrue(result['name']);self.assertEqual(result['status'],'In Progress')
        self.assertEqual(portal.list_interventions()['items'][0].student,self.student.name)
        portal.update_warning(warning,'Resolved')
        self.assertEqual(frappe.db.get_value('Student Warning',warning,'status'),'Resolved')
        self.assertEqual(frappe.db.get_value('Student Course Enrollment',self.enrollment.name,'attendance_standing'),'Barred')
        frappe.set_user(self.other_advisor.user)
        with self.assertRaises(frappe.PermissionError):portal.save_intervention(warning,'Unauthorized')
        with self.assertRaises(frappe.PermissionError):portal.update_warning(warning,'Open')

    def test_student_own_profile_only(self):
        frappe.set_user(self.student_user)
        result=portal.get_student_detail(self.student.name)
        self.assertFalse(result['can_advise']);self.assertEqual(result['interventions'],[])
        self.assertEqual(portal.get_overview()['profile'].name,self.student.name)
        for fn in [portal.list_students,portal.list_interventions,portal.get_catalog,portal.get_settings,portal.list_offerings]:
            with self.assertRaises(frappe.PermissionError):fn()

    def test_teacher_sees_only_assigned_courses(self):
        s=self.session(instructor=self.instructor.name)
        frappe.set_user(self.instructor.user)
        self.assertEqual([r.name for r in portal.list_offerings()['items']],[self.offering.name])
        self.assertEqual([r.name for r in portal.list_sessions()['items']],[s.name])
        with self.assertRaises(frappe.PermissionError):portal.get_student_detail(self.student.name)
        frappe.set_user(self.other_instructor.user)
        self.assertEqual(portal.list_offerings()['items'],[])
        self.assertEqual(portal.list_sessions()['items'],[])

    def test_catalog_admin_only_and_generated_records_protected(self):
        self.assertTrue(portal.get_catalog('Course')['editable'])
        self.assertFalse(portal.get_catalog('Student Warning')['editable'])
        r=portal.save_record('Course',dict(course_code=self.prefix+'NEW',course_name='New course',department=self.department.name,credits=3,course_type='Compulsory',status='Active'))
        self.assertTrue(frappe.db.exists('Course',r['name']))
        with self.assertRaises(frappe.ValidationError):portal.save_record('Student Warning',{})
        with self.assertRaises(frappe.ValidationError):portal.save_record('User',{})
        with self.assertRaises(frappe.ValidationError):portal.save_record('Course',{'ignore_permissions':True})
        frappe.set_user(self.instructor.user)
        with self.assertRaises(frappe.PermissionError):portal.save_record('Course',{})

    def test_context_roles_and_settings(self):
        with patch('frappe.sessions.get_csrf_token',return_value='test-token'):
            frappe.set_user(self.advisor.user);ctx=portal.get_context()
            self.assertTrue(ctx['roles']['advisor']);self.assertFalse(ctx['roles']['admin'])
            frappe.set_user(self.student_user);self.assertTrue(portal.get_context()['roles']['student'])
        frappe.set_user('Administrator')
        self.assertEqual(portal.get_settings()['barred_percentage'],20)
        with self.assertRaises(frappe.ValidationError):portal.save_settings({'default_total_sessions':30})

    def test_admin_can_use_student_advisor_when_warning_unassigned(self):
        s=self.session(slots=5,instructor=self.instructor.name);api.submit_bulk_attendance(s.name,self.data('Absent'))
        warning=frappe.db.get_value('Student Warning',{'student':self.student.name,'is_active':1},'name')
        frappe.db.set_value('Student Warning',warning,'assigned_to',None)
        result=portal.save_intervention(warning,'Quản trị ghi nhận hỗ trợ qua cố vấn phụ trách.')
        self.assertEqual(frappe.db.get_value('Intervention Log',result['name'],'advisor'),self.advisor.name)

if __name__=='__main__':
    frappe.init(site='studentcrm.local');frappe.connect();frappe.set_user('Administrator')
    try:result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PortalTests))
    finally:frappe.db.rollback();frappe.destroy()
    raise SystemExit(0 if result.wasSuccessful() else 1)
