"""CLI-only verification and safe finalization of a privately shared site copy."""
import hashlib
import json
import os
from pathlib import Path
import frappe
from frappe.utils.password import update_password

DOCTYPES=('Department','Program','Academic Term','Course','Faculty Member','Course Offering',
    'Class Session','Student','Student Course Enrollment','Student Attendance','Student Warning',
    'Student Support Case','Advisor Assignment','Intervention Log','Attendance Correction Request')
POLICY=('default_total_sessions','reminder_percentage','critical_percentage','barred_percentage',
        'near_limit_remaining','behavioral_consecutive_sessions','behavioral_window_days')


def audit():
    if frappe.session.user!='Administrator':frappe.throw('Administrator required.',frappe.PermissionError)
    counts={};digests={}
    for dt in DOCTYPES:
        fields=['name']+[f.fieldname for f in frappe.get_meta(dt).fields if f.fieldtype not in
            ('Section Break','Column Break','Tab Break','HTML','Button','Table','Table MultiSelect','Fold')]
        rows=frappe.get_all(dt,fields=list(dict.fromkeys(fields)),order_by='name asc',limit_page_length=0)
        counts[dt]=len(rows)
        digests[dt]=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
    settings=frappe.get_single('CRM Settings')
    return dict(counts=counts,digests=digests,policy={f:settings.get(f) for f in POLICY})


def verify_snapshot(manifest):
    expected=json.loads(Path(manifest).read_text(encoding='utf-8'))['business_snapshot']
    actual=audit()
    if actual!=expected:
        differences=[dt for dt in DOCTYPES if actual['counts'][dt]!=expected['counts'][dt] or actual['digests'][dt]!=expected['digests'][dt]]
        frappe.throw('Restored business data differs from snapshot: '+', '.join(differences or ['CRM Settings']))
    return dict(passed=True,counts=actual['counts'],policy=actual['policy'])


def finalize_copy(manifest):
    """Only on a target site explicitly marked by restore_copy.py; no source changes."""
    if not frappe.conf.get('crm_transfer_restore'):
        frappe.throw('Not a marked restore target. Refusing credential/session changes.')
    result=verify_snapshot(manifest)
    password=os.environ.get('CRM_TRANSFER_ADMIN_PASSWORD')
    if not password or len(password)<10:frappe.throw('A new Administrator password of at least 10 characters is required.')
    update_password('Administrator',password,logout_all_sessions=True)
    # Clear copied sessions and integration credentials; never contact source services.
    frappe.db.sql('delete from `tabSessions`')
    frappe.db.sql('update `tabUser` set api_key=NULL,api_secret=NULL')
    frappe.db.sql("delete from `__Auth` where doctype='User' and fieldname='api_secret'")
    for dt in ('OAuth Bearer Token','OAuth Authorization Code','Email Queue Recipient','Email Queue'):
        if frappe.db.exists('DocType',dt):frappe.db.delete(dt)
    if frappe.db.exists('DocType','Email Account'):
        fields={f:0 for f in ('enable_incoming','enable_outgoing','default_incoming','default_outgoing')
                if frappe.get_meta('Email Account').has_field(f)}
        for name in frappe.get_all('Email Account',pluck='name'):
            frappe.db.set_value('Email Account',name,fields,update_modified=False)
    frappe.clear_cache()
    return result
