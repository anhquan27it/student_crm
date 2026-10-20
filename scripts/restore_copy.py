"""Restore an encrypted full copy into a NEW Frappe-only site. Never run on a used site."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import frappe
from site_transfer import unpack


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',required=True)
    parser.add_argument('--package',required=True)
    parser.add_argument('--key-file',required=True)
    parser.add_argument('--db-root-username',default='root')
    args=parser.parse_args()
    bench=Path.cwd().resolve()
    if not (bench/'apps/frappe').is_dir() or not (bench/'sites').is_dir():raise ValueError('Run from frappe-bench.')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]+',args.site):raise ValueError('Invalid site name.')
    sites=bench/'sites';site=sites/args.site;config=site/'site_config.json'
    if not config.is_file():raise ValueError('Create a new site with bench new-site first.')
    os.chdir(sites);frappe.init(site=args.site,sites_path=str(sites));frappe.connect();frappe.set_user('Administrator')
    try:
        if set(frappe.get_installed_apps())!={'frappe'} or frappe.db.count('User')!=2:
            raise ValueError('Target must be a NEW site with only frappe and Administrator/Guest. Existing/demo sites are refused.')
    finally:frappe.db.rollback();frappe.destroy();os.chdir(bench)
    destination=site/'private'/('transfer-unpacked-'+uuid.uuid4().hex)
    try:
        manifest=unpack(Path(args.package).resolve(),Path(args.key_file).expanduser().resolve(),destination)
        if frappe.__version__!=manifest['frappe_version']:
            raise ValueError('Use Frappe '+manifest['frappe_version']+' for this exact copy; current version is '+frappe.__version__)
        new_password=os.environ.get('CRM_TRANSFER_ADMIN_PASSWORD')
        if not new_password:
            new_password=getpass.getpass('New Administrator password for YOUR copy (10+ characters): ')
            if getpass.getpass('Confirm new password: ')!=new_password:raise ValueError('Passwords do not match.')
        if len(new_password)<10:raise ValueError('New Administrator password must contain 10+ characters.')
        root_password=os.environ.get('CRM_TRANSFER_DB_PASSWORD')
        if root_password is None:root_password=getpass.getpass('MariaDB administrator password on YOUR machine: ')
        secrets_conf=json.loads((destination/'site-secrets.json').read_text())
        def configure(marked=True):
            conf=json.loads(config.read_text())
            # Keep destination db_name/password/host/port; never copy source DB credentials.
            conf.update(encryption_key=secrets_conf['encryption_key'],mute_emails=1,pause_scheduler=1)
            if marked:conf['crm_transfer_restore']=True
            else:conf.pop('crm_transfer_restore',None)
            config.write_text(json.dumps(conf,indent=2)+'\n');os.chmod(config,0o600)
        configure()
        env=dict(os.environ,CRM_TRANSFER_ADMIN_PASSWORD=new_password)
        def run(command):
            process=subprocess.run(command,cwd=bench,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            output=process.stdout.replace(new_password,'[redacted]')
            if root_password:output=output.replace(root_password,'[redacted]')
            print('\n'.join(line for line in output.splitlines() if 'Updating DocTypes for ' not in line),flush=True)
            if process.returncode:raise RuntimeError('Restore step failed. Target is a dedicated copy site; source was not touched.')
        run(['bench','--site',args.site,'restore',str(destination/'database.sql.gz'),
            '--with-public-files',str(destination/'public-files.tgz'),'--with-private-files',str(destination/'private-files.tgz'),
            '--db-root-username',args.db_root_username,'--db-root-password',root_password])
        configure()
        run(['bench','--site',args.site,'migrate','--skip-search-index'])
        run(['bench','--site',args.site,'execute','student_crm.transfer.finalize_copy','--kwargs',json.dumps({'manifest':str(destination/'manifest.json')})])
        configure(marked=False)
        (site/'private/frontend.env').write_text('PORT=5173\nHOST=127.0.0.1\nFRAPPE_URL=http://127.0.0.1:8000\nFRAPPE_SITE='+args.site+'\n')
        print('RESTORE VERIFIED: full business data matches. New Administrator password applied; copied sessions/API tokens cleared.')
        print('Mail and scheduler remain paused for this independent local copy.')
        print('Frontend config prepared at sites/'+args.site+'/private/frontend.env')
    finally:
        if destination.exists():
            if destination.resolve().parent!=(site/'private').resolve() or not destination.name.startswith('transfer-unpacked-'):
                raise RuntimeError('Unsafe cleanup path')
            shutil.rmtree(destination)


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Do not include subprocess arguments or cryptographic material in errors.
        print('Restore did not complete: '+str(error))
        raise SystemExit(1)
