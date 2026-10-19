"""Portable synthetic dataset. Run only with `bench --site SITE execute student_crm.demo.seed`.

No SQL dump, real students or Administrator password is included. A completed seed
is audited on subsequent calls; existing accounts/data are never overwritten.
"""
import json
import os
from pathlib import Path
from collections import Counter
import frappe
from frappe.utils import add_days,add_to_date,getdate,today,now_datetime
from frappe.utils.password import update_password
from student_crm.attendance_service import defer_refresh

PREFIX='DEMO-20261019'
SCENARIOS=['Good','Warning','Critical','Boundary 20%','Barred','Behavioral','Recovered','Late Only']


def _path():
    return Path(frappe.get_site_path('private','student_crm_demo','manifest.json'))


def _create(doctype,**values):
    return frappe.get_doc(dict(doctype=doctype,**values)).insert(ignore_permissions=True)


def _user(email,name,password):
    if frappe.db.exists('User',email):
        frappe.throw('Demo account already exists without a completed manifest: '+email)
    # Bulk fixture creation only; do not alter the web signup throttle.
    previous=frappe.flags.in_import
    try:
        frappe.flags.in_import=True
        _create('User',email=email,first_name=name,user_type='Website User',enabled=1,
                send_welcome_email=0,language='vi')
        update_password(email,password,logout_all_sessions=False)
    finally:
        frappe.flags.in_import=previous


def _status(scenario,local_course,number):
    absences={1:{2,4},2:{2,4,6},3:{1,3,5,7},4:{1,2,4,6,8},6:{2,4}}
    if local_course==0 and number in absences.get(scenario,set()):return 'Absent'
    if scenario==5 and number==8 and local_course in (2,3,4):return 'Absent'
    if scenario==7 and number in (2,5,7):return 'Late'
    return 'Present'


def seed(anchor_date=None):
    """Create 100 students, 15 requested courses, 500 enrollments, 4000 attendance rows.

    CLI-only, commits once after validation. CRM_DEMO_PASSWORD overrides the public
    local-demo password. Reruns audit the saved manifest without resetting passwords.
    """
    from student_crm import portal,support
    if frappe.session.user!='Administrator':frappe.throw('Run this fixture as Administrator.',frappe.PermissionError)
    path=_path()
    if path.exists():return verify()
    anchor=getdate(anchor_date or today())
    if anchor>getdate(today()):frappe.throw('Demo anchor cannot be in the future.')
    if frappe.db.exists('Academic Term',PREFIX+'-FALL') or frappe.db.exists('Student',PREFIX+'-SV001'):
        frappe.throw('Demo namespace already exists without this installer manifest. Use a new site; no existing data was changed.')
    settings=frappe.get_single('CRM Settings')
    expected=(10,15,20,3,14)
    actual=tuple(settings.get(x) for x in ['reminder_percentage','critical_percentage','barred_percentage','behavioral_consecutive_sessions','behavioral_window_days'])
    if actual!=expected:frappe.throw('Demo scenarios require default thresholds 10/15/20 and behavioral rule 3 sessions/14 days.')
    password=os.environ.get('CRM_DEMO_PASSWORD','Student@123')
    if len(password)<8:frappe.throw('CRM_DEMO_PASSWORD must contain at least 8 characters.')
    catalog=json.loads(Path(frappe.get_app_path('student_crm','demo_data','catalog.json')).read_text(encoding='utf-8'))
    manifest=dict(version=1,prefix=PREFIX,anchor=str(anchor),students=[],offerings=[],sessions=[],courses=[],interventions=[])
    term_start=add_days(anchor,-60);term_end=add_days(anchor,120)
    try:
        department=_create('Department',department_code=PREFIX+'-IT',department_name=PREFIX+' - Khoa Công nghệ thông tin',status='Active')
        programs=[_create('Program',program_code=PREFIX+'-'+code,program_name='DEMO - '+name,
            department=department.name,degree_level='Bachelor',duration_years=4,total_required_credits=130,status='Active')
            for code,name in [('SE','Software Engineering'),('AI','Artificial Intelligence'),('IS','Information Systems')]]
        term=_create('Academic Term',term_code=PREFIX+'-FALL',term_name='DEMO - Học kỳ mẫu',
            academic_year=f'{anchor.year}-{anchor.year+1}',start_date=term_start,end_date=term_end,status='In Progress',is_current=0)
        manifest['term']=term.name
        faculty=[]
        for i,name in enumerate(catalog['FACULTY_NAMES']):
            email=f'demo.crm.faculty{i+1:02d}@example.com';_user(email,name,password)
            faculty.append(_create('Faculty Member',user=email,faculty_code=PREFIX+f'-GV{i+1:02d}',full_name=name,
                department=department.name,is_advisor=int(i<3),is_instructor=int(i>=3),status='Active'))
        for code,name,semester in catalog['COURSES']:
            if frappe.db.exists('Course',code):
                if frappe.db.get_value('Course',code,'course_name')!=name:frappe.throw('Conflicting course: '+code)
            else:
                _create('Course',course_code=code,course_name=name,department=department.name,credits=3,
                    course_type='Compulsory',status='Active',description=f'Synthetic demo. Recommended curriculum semester: {semester}.')
            manifest['courses'].append(code)
        groups=[[],[],[]]
        for i in range(100):
            group=i%3;scenario=(i//3)%8;sid=PREFIX+f'-SV{i+1:03d}';email=f'demo.crm.student{i+1:03d}@example.com'
            base=catalog['NAMES'][i%len(catalog['NAMES'])]
            name=base if i<24 else base+f' {i+1:03d}'
            _user(email,name,password)
            _create('Student',id_student=sid,student_name=name,user=email,email=email,program=programs[group].name,
                admission_term=term.name,advisor=faculty[group].name,date_of_birth=f'2006-{i%12+1:02d}-{i%26+1:02d}',
                gender='Female' if i%2 else 'Male',enrollment_date=term_start,expected_graduation_date=add_days(anchor,1460),
                student_status='Active',address='Địa chỉ giả lập',notes='Synthetic demo person; '+SCENARIOS[scenario])
            item=dict(id=sid,name=name,user=email,group=group,scenario_index=scenario,scenario=SCENARIOS[scenario])
            groups[group].append(item);manifest['students'].append(item)
        print('Creating 15 classes, 300 sessions and 4000 attendance records...',flush=True)
        with defer_refresh():
            for index,(code,name,semester) in enumerate(catalog['COURSES']):
                group=index//5;local=index%5;hour=[7,12,17][group]+local
                offering=_create('Course Offering',offering_code=PREFIX+'-'+code,course=code,academic_term=term.name,
                    program=programs[group].name,section=f'DEMO-G{group+1}',class_name=f'DEMO {code} - Group {group+1}',
                    instructor=faculty[3+local].name,room=f'DEMO-A{group+1}0{local+1}',capacity=40,
                    start_date=term_start,end_date=term_end,total_slots=20,hours_per_slot=1,status='In Progress')
                manifest['offerings'].append(offering.name)
                for item in groups[group]:
                    _create('Student Course Enrollment',student=item['id'],course_offering=offering.name,enrollment_date=term_start,status='Enrolled')
                for number in range(1,21):
                    day=add_days(anchor,[-18,-16,-14,-12,-10,-8,-4,-1][number-1] if number<=8 else 2+2*(number-9))
                    session=_create('Class Session',session_id=PREFIX+'-'+code+f'-S{number:02d}',course_offering=offering.name,
                        session_no=number,session_date=day,start_time=f'{hour:02d}:00:00',end_time=f'{hour+1:02d}:00:00',
                        instructor=offering.instructor,room=offering.room,slot_count=1,session_type='Regular',delivery_mode='Offline',
                        status='Completed' if number<=8 else 'Scheduled',topic=f'DEMO {code} - Topic {number}')
                    manifest['sessions'].append(session.name)
                    if number<=8:
                        for item in groups[group]:
                            status=_status(item['scenario_index'],local,number)
                            _create('Student Attendance',student=item['id'],attendance_session=session.name,status=status,
                                late_minutes=10 if status=='Late' else 0,remarks='Synthetic demonstration attendance')
                        session.attendance_finalized=1;session.save(ignore_permissions=True)
        # Keep a warning history for recovered examples, then correct the original result.
        for item in manifest['students']:
            scenario=item['scenario_index'];group=item['group']
            if scenario==6:
                code=catalog['COURSES'][group*5][0]
                session=frappe.get_doc('Class Session',PREFIX+'-'+code+'-S04')
                session.attendance_finalized=0;session.save(ignore_permissions=True)
                attendance=frappe.get_doc('Student Attendance',{'student':item['id'],'attendance_session':session.name})
                attendance.status='Late';attendance.late_minutes=8;attendance.save(ignore_permissions=True)
                session.reload();session.attendance_finalized=1;session.save(ignore_permissions=True)
            if scenario in (4,5,6):
                kind='Behavioral-Level' if scenario==5 else 'Course-Level'
                warning=frappe.db.get_value('Student Warning',{'student':item['id'],'warning_type':kind,
                    'severity':{4:'Barred',5:'Critical',6:'Warning'}[scenario]},'name')
                if not warning:frappe.throw('Missing demo scenario warning: '+item['id'])
                log=portal.save_intervention(warning,summary='DỮ LIỆU MẪU: Đã liên hệ và thống nhất kế hoạch hỗ trợ.',
                    action_plan='Theo dõi chuyên cần, liên hệ lại sau 3 ngày.',outcome={4:'Escalated',5:'Monitoring',6:'Improved'}[scenario],
                    contacted_at=add_to_date(now_datetime(),minutes=-1),next_follow_up_date=add_days(today(),3))
                manifest['interventions'].append(log['name'])
                if scenario==6:
                    case=frappe.get_doc('Student Support Case',frappe.db.get_value('Student Warning',warning,'support_case'))
                    support.update_case(case.name,'Closed',priority='Normal',resolution_summary='DỮ LIỆU MẪU: Đã đối chiếu và sửa kết quả điểm danh.',expected_modified=str(case.modified))
        result=_verify(manifest,check_scenarios=True)
        path.parent.mkdir(parents=True,exist_ok=True)
        pending=path.with_suffix('.pending.json');pending.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        frappe.db.commit();pending.replace(path)
        return result
    except BaseException:
        frappe.db.rollback()
        raise


def _verify(manifest,check_scenarios=False):
    ids=[x['id'] for x in manifest['students']]
    counts={dt:frappe.db.count(dt,{'student':['in',ids]}) for dt in ['Student Course Enrollment','Student Attendance']}
    assert len(ids)==100 and frappe.db.count('Student',{'name':['in',ids]})==100
    assert counts['Student Course Enrollment']==500 and counts['Student Attendance']==4000
    assert frappe.db.count('Class Session',{'name':['in',manifest['sessions']]})==300
    assert frappe.db.count('Student Attendance',{'student':['in',ids],'enrollment':['is','not set']})==0
    if check_scenarios:
        for item in manifest['students']:
            e=frappe.db.get_value('Student Course Enrollment',{'student':item['id'],
                'course_offering':manifest['offerings'][item['group']*5]},['absent_count','attendance_standing'],as_dict=True)
            n=item['scenario_index']
            assert e.absent_count==[0,2,3,4,5,0,1,0][n],(item,e)
            assert e.attendance_standing==['Good','Warning','Critical','Critical','Barred','Good','Good','Good'][n],(item,e)
    advisors=Counter(frappe.db.get_value('Student',sid,'advisor') for sid in ids)
    assert sorted(advisors.values())==[33,33,34]
    return dict(passed=True,students=100,courses=15,offerings=15,sessions=300,enrollments=500,attendance=4000,
                by_advisor=dict(advisors),anchor=manifest['anchor'])


def verify():
    """Audit record links/counts; does not reset passwords, attendance or warning history."""
    if frappe.session.user!='Administrator':frappe.throw('Administrator required.',frappe.PermissionError)
    if not _path().exists():frappe.throw('No portable demo manifest. Run student_crm.demo.seed on a new site.')
    return _verify(json.loads(_path().read_text(encoding='utf-8')))
