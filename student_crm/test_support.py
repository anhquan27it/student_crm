import unittest
import frappe
from frappe.utils import today,add_days,now_datetime
from student_crm import api,portal,support
from student_crm.tests.test_api import StudentCRMApiTests as F


class SupportTests(unittest.TestCase):
    create=F.create;offering_for=F.offering_for;enroll=F.enroll;session=F.session;record=F.record;finalize=F.finalize
    faculty=F.faculty;data=F.data;setUp=F.setUp;tearDown=F.tearDown

    def warning_case(self,slots=5):
        session=self.session(slots=slots,instructor=self.instructor.name)
        api.submit_bulk_attendance(session.name,self.data('Absent'))
        name=frappe.db.get_value('Student Support Case',{'student':self.student.name},'name')
        return session,frappe.get_doc('Student Support Case',name)

    def test_case_links_warnings_and_interventions_and_keeps_barred(self):
        session,case=self.warning_case()
        self.assertEqual(case.owner_advisor,self.advisor.name)
        self.assertEqual(case.priority,'Urgent')
        warning=frappe.db.get_value('Student Warning',{'student':self.student.name,'is_active':1},'name')
        self.assertEqual(frappe.db.get_value('Student Warning',warning,'support_case'),case.name)
        frappe.set_user(self.advisor.user)
        result=portal.save_intervention(warning,'Thống nhất kế hoạch hỗ trợ.',next_follow_up_date=today())
        self.assertEqual(frappe.db.get_value('Intervention Log',result['name'],'support_case'),case.name)
        case.reload();self.assertEqual(case.status,'In Progress')
        self.assertEqual(case.target_date,frappe.utils.getdate(today()))
        support.update_case(case.name,'Closed',resolution_summary='Đã tư vấn, tiếp tục theo dõi.',expected_modified=str(case.modified))
        self.assertEqual(frappe.db.get_value('Student Course Enrollment',self.enrollment.name,'attendance_standing'),'Barred')
        self.assertEqual(frappe.db.get_value('ToDo',{'reference_type':'Student Support Case','reference_name':case.name,'allocated_to':self.advisor.user},'status'),'Closed')

    def test_case_grouping_and_scope(self):
        session,case=self.warning_case()
        second=self.offering_for('second');self.enroll(second)
        s=self.session(offering=second,slots=3,instructor=self.instructor.name)
        api.submit_bulk_attendance(s.name,self.data('Absent'))
        self.assertEqual(frappe.db.count('Student Support Case',{'student':self.student.name}),1)
        frappe.set_user(self.other_advisor.user)
        self.assertFalse(any(r.student==self.student.name for r in support.list_cases()['items']))
        with self.assertRaises(frappe.PermissionError):support.get_case(case.name)
        with self.assertRaises(frappe.PermissionError):support.assignment_history(self.student.name)
        frappe.set_user(self.student_user)
        with self.assertRaises(frappe.PermissionError):support.get_support_dashboard()

    def test_assignment_transfers_ownership_and_keeps_history(self):
        session,case=self.warning_case();self.student.reload()
        support.assign_advisor(self.student.name,self.other_advisor.name,'Chuyển cố vấn phụ trách.',expected_modified=str(self.student.modified))
        history=support.assignment_history(self.student.name)['items']
        self.assertEqual(len(history),2)
        self.assertEqual(sum(not x.effective_to for x in history),1)
        case.reload();self.assertEqual(case.owner_advisor,self.other_advisor.name)
        self.assertEqual(frappe.db.get_value('ToDo',{'reference_name':case.name,'allocated_to':self.advisor.user},'status'),'Cancelled')
        frappe.set_user(self.advisor.user)
        with self.assertRaises(frappe.PermissionError):support.get_case(case.name)
        frappe.set_user(self.other_advisor.user)
        self.assertEqual(support.get_case(case.name)['case']['owner_advisor'],self.other_advisor.name)

    def test_student_request_teacher_approval_recalculates_metrics(self):
        session,case=self.warning_case()
        attendance=frappe.db.get_value('Student Attendance',{'student':self.student.name,'attendance_session':session.name},'name')
        frappe.set_user(self.student_user)
        result=support.request_correction(attendance,'Present','Tôi đã có mặt, đề nghị đối chiếu.')
        with self.assertRaises(frappe.ValidationError):support.request_correction(attendance,'Present','Trùng yêu cầu')
        request=frappe.get_doc('Attendance Correction Request',result['name'])
        with self.assertRaises(frappe.PermissionError):support.review_correction(request.name,'Approved','Không được tự duyệt',str(request.modified))
        frappe.set_user(self.other_instructor.user)
        with self.assertRaises(frappe.PermissionError):support.review_correction(request.name,'Approved','Sai giảng viên',str(request.modified))
        frappe.set_user(self.instructor.user)
        support.review_correction(request.name,'Approved','Đã đối chiếu danh sách.',str(request.modified))
        self.assertEqual(frappe.db.get_value('Student Attendance',attendance,'status'),'Present')
        self.assertEqual(frappe.db.get_value('Student Course Enrollment',self.enrollment.name,'absent_count'),0)
        self.assertEqual(frappe.db.get_value('Class Session',session.name,'attendance_finalized'),1)
        self.assertEqual(frappe.db.get_value('Attendance Correction Request',request.name,'reviewed_by'),self.instructor.user)

    def test_stale_request_never_overwrites_new_attendance(self):
        session,case=self.warning_case()
        attendance=frappe.db.get_value('Student Attendance',{'student':self.student.name,'attendance_session':session.name},'name')
        frappe.set_user(self.student_user)
        result=support.request_correction(attendance,'Present','Đề nghị đối chiếu.')
        request=frappe.get_doc('Attendance Correction Request',result['name'])
        frappe.set_user(self.instructor.user);session.reload()
        api.submit_bulk_attendance(session.name,self.data('Late',late_minutes=5),str(session.modified))
        with self.assertRaises(frappe.TimestampMismatchError):support.review_correction(request.name,'Approved','Đã đối chiếu',str(request.modified))
        self.assertEqual(frappe.db.get_value('Student Attendance',attendance,'status'),'Late')
        support.review_correction(request.name,'Rejected','Dữ liệu đã được sửa trực tiếp.',str(request.modified))
        self.assertEqual(frappe.db.get_value('Attendance Correction Request',request.name,'status'),'Rejected')

    def test_notifications_scope_and_followup_dedup(self):
        session,case=self.warning_case();case.target_date=today();case.flags.support_internal=True;case.save(ignore_permissions=True)
        support.daily_followups();support.daily_followups()
        frappe.set_user(self.advisor.user)
        logs=support.list_notifications()['items']
        matches=[x for x in logs if x.document_name==case.name]
        self.assertEqual(len(matches),1)
        support.mark_notification_read(matches[0].name)
        frappe.set_user(self.other_advisor.user)
        with self.assertRaises(frappe.PermissionError):support.mark_notification_read(matches[0].name)

    def test_report_handles_empty_and_contacted_cohorts(self):
        self.warning_case()
        warning=frappe.db.get_value('Student Warning',{'student':self.student.name,'is_active':1},'name')
        frappe.set_user(self.advisor.user)
        empty=support.get_support_dashboard();self.assertEqual(empty['summary'].total,1)
        portal.save_intervention(warning,'Đã liên hệ thành công.')
        report=support.get_support_dashboard()
        self.assertEqual(report['measurement']['observed_cases'],1)
        self.assertEqual(report['measurement']['matured_cases'],0)
        self.assertIsNone(report['measurement']['return_rate'])

    def test_direct_derived_record_write_and_missing_version_denied(self):
        session,case=self.warning_case()
        with self.assertRaises(frappe.TimestampMismatchError):support.update_case(case.name,'Closed',resolution_summary='Kết quả')
        with self.assertRaises(frappe.ValidationError):
            self.create('Advisor Assignment',student=self.student.name,advisor=self.other_advisor.name,
                effective_from=now_datetime(),assignment_reason='Bypass',recorded_by='Administrator',recorded_at=now_datetime())

    def test_matured_cohort_detects_return_within_fourteen_days(self):
        session,case=self.warning_case()
        warning=frappe.db.get_value('Student Warning',{'student':self.student.name,'is_active':1},'name')
        portal.save_intervention(warning,'Contacted twenty days ago.',contacted_at=add_days(now_datetime(),-20))
        attended=self.session(number=2,days=-10,instructor=self.instructor.name)
        api.submit_bulk_attendance(attended.name,self.data('Present'))
        frappe.set_user(self.advisor.user)
        report=support.get_support_dashboard()['measurement']
        self.assertEqual(report['matured_cases'],1)
        self.assertEqual(report['returned_cases'],1)
        self.assertEqual(report['return_rate'],100)

    def test_closed_case_stays_closed_until_a_new_signal(self):
        session,case=self.warning_case()
        support.update_case(case.name,'Closed',resolution_summary='Support completed.',expected_modified=str(case.modified))
        from student_crm.attendance_service import refresh_offering
        refresh_offering(self.offering.name)
        case.reload();self.assertEqual(case.status,'Closed')
        warning=frappe.get_doc('Student Warning',frappe.db.get_value('Student Warning',{'student':self.student.name,'is_active':1},'name'))
        warning.flags.support_bootstrap=True;support.warning_changed(warning)
        case.reload();self.assertEqual(case.status,'Closed')
