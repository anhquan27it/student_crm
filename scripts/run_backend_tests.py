"""Run rollback-only CRM tests using the bench virtualenv on a dedicated test site."""
import argparse
import os
import unittest
from pathlib import Path
from unittest.mock import patch
import frappe

parser=argparse.ArgumentParser()
parser.add_argument('--site',required=True)
parser.add_argument('--sites-path',default=str(Path.cwd()/'sites'))
args=parser.parse_args()
sites_path=Path(args.sites_path).resolve()
os.chdir(sites_path)
frappe.init(site=args.site,sites_path=str(sites_path))
frappe.connect();frappe.set_user('Administrator')
try:
    suite=unittest.TestSuite()
    for module in [
        'student_crm.tests.test_attendance_rules.UniversityAttendanceTests',
        'student_crm.tests.test_api.StudentCRMApiTests',
        'student_crm.tests.test_portal.PortalTests',
        'student_crm.test_support.SupportTests',
        'student_crm.test_experience.ExperienceTests',
        'student_crm.test_full_qa.FullQATests',
    ]:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
    with patch('frappe.core.doctype.user.user.throttle_user_creation'):
        result=unittest.TextTestRunner(verbosity=2).run(suite)
finally:
    frappe.db.rollback();frappe.destroy()
raise SystemExit(0 if result.wasSuccessful() else 1)
