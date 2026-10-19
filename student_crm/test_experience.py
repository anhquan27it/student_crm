import unittest
import frappe
from frappe.utils import today,add_days
from student_crm import experience,api,portal,support
from student_crm.tests.test_api import StudentCRMApiTests as F


class ExperienceTests(unittest.TestCase):
    create=F.create;offering_for=F.offering_for;enroll=F.enroll;session=F.session;record=F.record;finalize=F.finalize
    faculty=F.faculty;data=F.data;setUp=F.setUp;tearDown=F.tearDown

    def test_workbench_is_distinct_and_scoped_for_every_role(self):
        session=self.session(slots=5,instructor=self.instructor.name,days=0)
        api.submit_bulk_attendance(session.name,self.data('Absent'))
        self.assertEqual(experience.get_workbench()['role'],'admin')
        frappe.set_user(self.advisor.user)
        result=experience.get_workbench(self.term.name)
        self.assertEqual(result['role'],'advisor');self.assertEqual(result['summary']['urgent'],1)
        self.assertEqual(result['urgent'][0].student,self.student.name)
        frappe.set_user(self.other_advisor.user)
        self.assertEqual(experience.get_workbench()['summary']['active'],0)
        frappe.set_user(self.instructor.user)
        result=experience.get_workbench(self.term.name)
        self.assertEqual(result['role'],'instructor');self.assertEqual(result['summary']['today_sessions'],1)
        self.assertEqual(result['today_sessions'][0].name,session.name)
        frappe.set_user(self.student_user)
        result=experience.get_workbench(self.term.name)
        self.assertEqual(result['role'],'student');self.assertEqual(result['advisor'].full_name,self.advisor.full_name)
        self.assertEqual(result['enrollments'][0].attendance_standing,'Barred')
        self.assertNotIn('interventions',result)
        frappe.set_user('Guest')
        with self.assertRaises(frappe.PermissionError):experience.get_workbench()

    def test_terms_and_student_totals_are_limited_to_the_selected_term(self):
        first=self.session(slots=5,instructor=self.instructor.name)
        api.submit_bulk_attendance(first.name,self.data('Absent'))
        term=self.create('Academic Term',term_code=self.prefix+'-NEXT',term_name='Second term',academic_year='2026-2027',
            start_date=add_days(today(),-30),end_date=add_days(today(),90),status='In Progress')
        offering=self.create('Course Offering',offering_code=self.prefix+'-NEXT',course=self.course.name,academic_term=term.name,status='In Progress',instructor=self.instructor.name)
        self.enroll(offering)
        second=self.session(offering=offering,slots=1,instructor=self.instructor.name)
        api.submit_bulk_attendance(second.name,self.data('Present'))
        frappe.set_user(self.advisor.user)
        selected=portal.list_students(academic_term=term.name,risk_standing='Good')
        self.assertEqual(selected['total_count'],1)
        self.assertEqual(selected['items'][0].risk_standing,'Good')
        self.assertEqual(selected['items'][0].attendance_rate,100)
        self.assertEqual(portal.list_students(academic_term=term.name,risk_standing='Barred')['total_count'],0)
        self.assertEqual(api.get_advisor_dashboard(academic_term=term.name)['summary']['warnings']['active_warnings'],0)
        self.assertEqual(api.get_advisor_dashboard(academic_term=self.term.name)['summary']['warnings']['active_warnings'],1)
        frappe.set_user(self.student_user)
        self.assertEqual(len(experience.get_terms()['items']),2)
        profile=portal.get_student_detail(self.student.name,academic_term=term.name)
        self.assertEqual(profile['profile'].total_absent,0)
        self.assertEqual(profile['profile'].risk_standing,'Good')
        self.assertEqual(len(profile['enrollments']),1)
        frappe.set_user(self.other_advisor.user)
        self.assertEqual(experience.get_terms()['items'],[])

    def test_case_status_filters_preserve_access_and_deadlines(self):
        session=self.session(slots=5,instructor=self.instructor.name)
        api.submit_bulk_attendance(session.name,self.data('Absent'))
        case=frappe.get_doc('Student Support Case',{'student':self.student.name})
        # Use a date at/after case opening; tomorrow's date must survive a risk refresh.
        case.target_date=add_days(today(),4);case.flags.support_internal=True;case.save(ignore_permissions=True)
        frappe.set_user(self.advisor.user)
        self.assertEqual(support.list_cases(academic_term=self.term.name,status='urgent')['total_count'],1)
        self.assertEqual(support.list_cases(status='uncontacted')['total_count'],1)
        self.assertEqual(support.list_cases(status='Closed')['total_count'],0)
        self.assertEqual(support.list_cases(status='overdue')['total_count'],0)
        with self.assertRaises(frappe.ValidationError):support.list_cases(status='injected')
        frappe.set_user(self.other_advisor.user)
        self.assertEqual(support.list_cases(status='urgent')['total_count'],0)

    def test_corrections_and_attendance_filters_share_term_scope(self):
        s=self.session(instructor=self.instructor.name)
        api.submit_bulk_attendance(s.name,self.data('Absent'))
        a=frappe.db.get_value('Student Attendance',{'student':self.student.name,'attendance_session':s.name},'name')
        frappe.set_user(self.student_user)
        support.request_correction(a,'Present','Please verify.')
        self.assertEqual(len(support.list_my_attendance(academic_term=self.term.name,status='Absent')['items']),1)
        self.assertEqual(support.list_my_attendance(status='Present')['items'],[])
        self.assertEqual(support.list_corrections(academic_term=self.term.name,status='Pending')['total_count'],1)
        self.assertEqual(support.list_corrections(status='Rejected')['total_count'],0)
        frappe.set_user(self.instructor.user)
        self.assertEqual(experience.get_workbench()['summary']['pending_corrections'],1)

    def test_teacher_date_filters_and_notification_count(self):
        self.session(number=1,days=0,instructor=self.instructor.name)
        self.session(number=2,days=2,instructor=self.instructor.name)
        self.session(number=3,days=-1,instructor=self.instructor.name)
        frappe.set_user(self.instructor.user)
        self.assertEqual(len(portal.list_sessions(academic_term=self.term.name,date_scope='today')['items']),1)
        self.assertEqual(len(portal.list_sessions(date_scope='upcoming')['items']),1)
        self.assertEqual(len(portal.list_sessions(date_scope='past',attendance_filter='pending')['items']),2)
        self.assertEqual(experience.unread_count()['unread'],0)
        with self.assertRaises(frappe.ValidationError):portal.list_sessions(date_scope='bad')
