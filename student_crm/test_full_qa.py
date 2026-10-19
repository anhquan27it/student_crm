import unittest
import frappe
from frappe.utils import getdate
from student_crm import api,portal,support,experience
from student_crm.tests.test_api import StudentCRMApiTests as F


class FullQATests(unittest.TestCase):
    create=F.create;offering_for=F.offering_for;enroll=F.enroll;session=F.session;record=F.record;finalize=F.finalize
    faculty=F.faculty;data=F.data;setUp=F.setUp;tearDown=F.tearDown

    def test_catalog_updates_require_current_version(self):
        row=next(x for x in portal.get_catalog('Course',search=self.course.name)['items'] if x.name==self.course.name)
        self.assertTrue(row.modified)
        portal.save_record('Course',{'course_name':'QA updated'},self.course.name,str(row.modified))
        with self.assertRaises(frappe.TimestampMismatchError):
            portal.save_record('Course',{'course_name':'QA stale'},self.course.name,str(row.modified))
        with self.assertRaises(frappe.TimestampMismatchError):
            portal.save_record('Course',{'course_name':'QA missing'},self.course.name)
        self.assertEqual(frappe.db.get_value('Course',self.course.name,'course_name'),'QA updated')

    def test_pending_sessions_exclude_cancelled_and_postponed(self):
        active=self.session(number=1,instructor=self.instructor.name)
        for n,status in [(2,'Cancelled'),(3,'Postponed')]:
            session=self.session(number=n,instructor=self.instructor.name)
            session.status=status;session.save(ignore_permissions=True)
        frappe.set_user(self.instructor.user)
        names={x.name for x in portal.list_sessions(attendance_filter='pending')['items']}
        self.assertEqual(names,{active.name})
        self.assertEqual(len(experience.get_workbench()['pending_sessions']),1)

    def test_session_search_accepts_display_date_and_class_name(self):
        session=self.session(instructor=self.instructor.name)
        frappe.db.set_value('Course Offering',self.offering.name,'class_name','QA Unique Class')
        frappe.set_user(self.instructor.user)
        self.assertEqual(portal.list_sessions(search='QA Unique Class')['items'][0].name,session.name)
        date=getdate(session.session_date).strftime('%d/%m/%Y')
        self.assertEqual(portal.list_sessions(search=date)['items'][0].name,session.name)

    def test_direct_correction_and_notification_obey_owner_scope(self):
        session=self.session(instructor=self.instructor.name)
        api.submit_bulk_attendance(session.name,self.data('Absent'))
        attendance=frappe.db.get_value('Student Attendance',{'student':self.student.name,'attendance_session':session.name},'name')
        frappe.set_user(self.student_user)
        correction=support.request_correction(attendance,'Present','QA verify register')['name']
        self.assertFalse(support.get_correction(correction)['can_review'])
        frappe.set_user(self.instructor.user)
        row=support.get_correction(correction)
        self.assertTrue(row['can_review'])
        notification=next(x for x in support.list_notifications()['items'] if x.document_name==correction)
        self.assertEqual(support.get_notification(notification.name).document_name,correction)
        frappe.set_user(self.other_instructor.user)
        with self.assertRaises(frappe.PermissionError):support.get_correction(correction)
        with self.assertRaises(frappe.PermissionError):support.get_notification(notification.name)
