"""Install Student CRM support features; run after taking a site backup."""
import json
from pathlib import Path
import frappe


def field(name, kind='Data', options=None, required=False, readonly=False, default=None):
    value=dict(fieldname=name,label=name.replace('_',' ').title(),fieldtype=kind,
               reqd=int(required),read_only=int(readonly))
    if options is not None:value['options']=options
    if default is not None:value['default']=default
    return value


SCHEMAS={
 'Student Support Case':[
    field('student','Link','Student',True,True),field('academic_term','Link','Academic Term',False,True),
    field('case_key',readonly=True,required=True),field('owner_advisor','Link','Faculty Member',False,True),
    field('priority','Select','Normal\nHigh\nUrgent',True,default='High'),
    field('status','Select','Open\nIn Progress\nMonitoring\nClosed',True,default='Open'),
    field('opened_at','Datetime',readonly=True),field('target_date','Date'),
    field('support_plan','Text'),field('resolution_summary','Text'),field('closed_at','Datetime',readonly=True),
    field('baseline_attendance_rate','Percent',readonly=True),
 ],
 'Advisor Assignment':[
    field('student','Link','Student',True,True),field('advisor','Link','Faculty Member',True,True),
    field('academic_term','Link','Academic Term',readonly=True),
    field('effective_from','Datetime',required=True,readonly=True),field('effective_to','Datetime',readonly=True),
    field('assignment_reason','Small Text',required=True,readonly=True),
    field('recorded_by','Link','User',True,True),field('recorded_at','Datetime',required=True,readonly=True),
 ],
 'Attendance Correction Request':[
    field('attendance','Link','Student Attendance',True,True),field('student','Link','Student',True,True),
    field('class_session','Link','Class Session',True,True),field('requested_by','Link','User',True,True),
    field('requested_at','Datetime',required=True,readonly=True),
    field('original_status','Select','Present\nAbsent\nLate',True,True),
    field('original_late_minutes','Int',readonly=True),field('attendance_version','Datetime',required=True,readonly=True),
    field('requested_status','Select','Present\nAbsent\nLate',True,True),
    field('late_minutes','Int',readonly=True,default='0'),field('reason','Text',required=True,readonly=True),
    field('evidence','Text',readonly=True),
    field('status','Select','Pending\nApproved\nRejected',True,True,default='Pending'),
    field('reviewed_by','Link','User',readonly=True),field('reviewed_at','Datetime',readonly=True),
    field('review_note','Small Text',readonly=True),
 ]}


def install():
    if not frappe.db.exists('Notification Type','Student CRM'):
        frappe.get_doc(dict(doctype='Notification Type',type_name='Student CRM',enabled=1)).insert(ignore_permissions=True)
    folder=Path(frappe.get_app_path('student_crm','student_crm','doctype'))
    for name,fields in SCHEMAS.items():
        slug=frappe.scrub(name);path=folder/slug;path.mkdir(exist_ok=True)
        for f in fields:
            if f['fieldname']=='case_key':f['unique']=1
            if f['fieldname'] in ('student','status','advisor','owner_advisor','requested_status'):f['in_list_view']=1
        schema=dict(doctype='DocType',name=name,module='Student Crm',autoname='format:'+{'Student Support Case':'CASE','Advisor Assignment':'ADV','Attendance Correction Request':'COR'}[name]+'-{#####}',
            engine='InnoDB',track_changes=1,fields=fields,field_order=[f['fieldname'] for f in fields],
            permissions=[dict(role='System Manager',read=1,write=1,create=1,delete=0,report=1)],
            sort_field='modified',sort_order='DESC')
        (path/(slug+'.json')).write_text(json.dumps(schema,ensure_ascii=False,indent=2))
        (path/'__init__.py').touch()
        classname=name.replace(' ','')
        (path/(slug+'.py')).write_text('from frappe.model.document import Document\nfrom student_crm import support\n\nclass '+classname+'(Document):\n    def validate(self):\n        support.validate_document(self)\n    def on_trash(self):\n        support.prevent_delete(self)\n')
        frappe.reload_doc('student_crm','doctype',slug,force=True)
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({dt:[dict(fieldname='support_case',label='Support Case',fieldtype='Link',
        options='Student Support Case',read_only=1,insert_after='student')] for dt in ['Student Warning','Intervention Log']},ignore_validate=True)
    create_custom_fields({'Notification Log':[dict(fieldname='crm_event_key',label='CRM Event Key',
        fieldtype='Data',unique=1,hidden=1,read_only=1)]},ignore_validate=True)
    frappe.db.add_index('Student Support Case',['owner_advisor','status'],'advisor_case_status')
    frappe.db.add_index('Advisor Assignment',['student','effective_to'],'student_assignment_end')
    frappe.db.add_index('Attendance Correction Request',['attendance','status'],'attendance_correction_status')
    from student_crm import support
    existing_cases=set(frappe.get_all('Student Support Case',pluck='name'))
    for student in frappe.get_all('Student',filters={'advisor':['is','set']},pluck='name'):
        support.sync_assignment(frappe.get_doc('Student',student),reason='Initial snapshot at CRM support rollout; earlier dates are unknown.')
    for name in frappe.get_all('Student Warning',filters={'is_active':1},pluck='name'):
        warning=frappe.get_doc('Student Warning',name);warning.flags.support_bootstrap=True
        support.warning_changed(warning)
    # Preserve the full warning timeline inside cases created from active signals.
    for case in frappe.get_all('Student Support Case',fields=['name','student','academic_term']):
        for warning in frappe.get_all('Student Warning',filters={'student':case.student,
                'academic_term':case.academic_term or ['is','not set'],'support_case':['is','not set']},pluck='name'):
            frappe.db.set_value('Student Warning',warning,'support_case',case.name,update_modified=False)
    for name in frappe.get_all('Intervention Log',pluck='name'):
        log=frappe.get_doc('Intervention Log',name)
        log.flags.support_link_only=frappe.db.get_value('Student Warning',log.warning,'support_case') in existing_cases
        support.intervention_changed(log)
    quality=support.reconcile_legacy_attendance(apply=True)
    support.daily_followups()
    frappe.clear_cache()
    return dict(installed=list(SCHEMAS),legacy_reconciliation=quality)
