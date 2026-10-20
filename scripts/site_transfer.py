"""Encrypt/decrypt a site backup. Requires cryptography (available in Frappe's env)."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import tarfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC=b'STUDENT-CRM-TRANSFER-v1\n'
MEMBERS={'database.sql.gz','public-files.tgz','private-files.tgz','site-secrets.json','manifest.json'}


def pack(backup_dir,snapshot,output,key_out):
    backup_dir=Path(backup_dir);output=Path(output);key_out=Path(key_out)
    if output.exists() or key_out.exists():raise ValueError('Refusing to overwrite a package/key.')
    def one(pattern):
        matches=list(backup_dir.glob(pattern))
        if len(matches)!=1:raise ValueError('Expected exactly one backup: '+pattern)
        return matches[0]
    files={'database.sql.gz':one('*-database.sql.gz'),'private-files.tgz':one('*-private-files.tgz')}
    # Public pattern also matches private-files; select by exact suffix without private.
    public=[p for p in backup_dir.glob('*-files.tgz') if not p.name.endswith('-private-files.tgz')]
    if len(public)!=1:raise ValueError('Expected one public files archive.')
    files['public-files.tgz']=public[0]
    conf=json.loads(one('*-site_config_backup.json').read_text())
    if not conf.get('encryption_key'):raise ValueError('Source encryption_key is required.')
    manifest=json.loads(Path(snapshot).read_text())
    manifest['file_sha256']={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in files.items()}
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as archive:
        for name,p in files.items():archive.add(p,arcname=name,recursive=False)
        for name,value in [('site-secrets.json',{'encryption_key':conf['encryption_key']}),('manifest.json',manifest)]:
            data=json.dumps(value,ensure_ascii=False,indent=2).encode();member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600
            archive.addfile(member,io.BytesIO(data))
    key=AESGCM.generate_key(bit_length=256);nonce=secrets.token_bytes(12)
    encrypted=MAGIC+nonce+AESGCM(key).encrypt(nonce,payload.getvalue(),MAGIC)
    key_out.parent.mkdir(parents=True,exist_ok=True)
    with key_out.open('x',encoding='ascii') as f:f.write(base64.urlsafe_b64encode(key).decode()+'\n')
    os.chmod(key_out,0o600)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:f.write(encrypted)
    return dict(file=output.name,size=len(encrypted),sha256=hashlib.sha256(encrypted).hexdigest(),
        created_at=manifest['created_at'],frappe_version=manifest['frappe_version'],counts=manifest['business_snapshot']['counts'])


def unpack(package,key_file,destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Extraction destination must not exist.')
    raw=Path(package).read_bytes()
    if not raw.startswith(MAGIC):raise ValueError('Unknown encrypted package format.')
    key=base64.urlsafe_b64decode(Path(key_file).read_text().strip())
    if len(key)!=32:raise ValueError('Invalid transfer key.')
    nonce=raw[len(MAGIC):len(MAGIC)+12]
    plain=AESGCM(key).decrypt(nonce,raw[len(MAGIC)+12:],MAGIC)
    with tarfile.open(fileobj=io.BytesIO(plain),mode='r:gz') as archive:
        members=archive.getmembers()
        if len(members)!=5 or {m.name for m in members}!=MEMBERS or any(not m.isfile() for m in members):
            raise ValueError('Unexpected archive contents.')
        destination.mkdir(parents=True,mode=0o700)
        archive.extractall(destination,filter='data')
    manifest=json.loads((destination/'manifest.json').read_text())
    for name,expected in manifest['file_sha256'].items():
        if name not in MEMBERS or hashlib.sha256((destination/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Backup file integrity check failed.')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('pack');p.add_argument('--backup-dir',required=True);p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True);p.add_argument('--key-out',required=True)
    p=sub.add_parser('unpack');p.add_argument('--package',required=True);p.add_argument('--key-file',required=True);p.add_argument('--destination',required=True)
    args=vars(parser.parse_args());command=args.pop('command')
    try:
        result=pack(**args) if command=='pack' else unpack(**args)
        print(json.dumps(result if command=='pack' else {'verified':True,'counts':result['business_snapshot']['counts']},ensure_ascii=False))
    except Exception:
        raise SystemExit('Transfer failed. Check paths/key, destination freshness and package integrity; no secrets are printed.')
