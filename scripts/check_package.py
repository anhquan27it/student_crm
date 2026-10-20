"""Offline checks for packaged DocTypes and portable fixture data (no Frappe needed)."""
import json
import hashlib
from pathlib import Path

root=Path(__file__).resolve().parents[1]
schemas=list((root/'student_crm/student_crm/doctype').glob('*/*.json'))
assert len(schemas)==16,len(schemas)
for path in schemas:
    data=json.loads(path.read_text(encoding='utf-8'))
    assert data['module']=='Student Crm',path
    names=[f['fieldname'] for f in data['fields']]
    assert len(names)==len(set(names)),path
catalog=json.loads((root/'student_crm/demo_data/catalog.json').read_text(encoding='utf-8'))
assert len(catalog['COURSES'])==15
assert len({r[0] for r in catalog['COURSES']})==15
transfer=root/'transfer/latest.json'
if transfer.exists():
    info=json.loads(transfer.read_text())
    assert info['counts']['Student']==121
    package=root/'transfer'/info['file']
    assert package.stat().st_size==info['size']
    assert hashlib.sha256(package.read_bytes()).hexdigest()==info['sha256']
print('PASS: 16 DocType schemas and 15 demo courses packaged.')
