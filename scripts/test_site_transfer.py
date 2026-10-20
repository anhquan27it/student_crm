import base64
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from cryptography.exceptions import InvalidTag
from site_transfer import pack,unpack


class TransferEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.backup=self.root/'backup';self.backup.mkdir()
        for name,data in [('x-database.sql.gz',gzip.compress(b'private fixture SQL')),
                          ('x-files.tgz',b'public fixture'),('x-private-files.tgz',b'private fixture')]:
            (self.backup/name).write_bytes(data)
        (self.backup/'x-site_config_backup.json').write_text(json.dumps({'encryption_key':'fixture-key','db_password':'must-not-transfer'}))
        self.snapshot=self.root/'audit.json';self.snapshot.write_text(json.dumps({'created_at':'2026-10-20',
            'frappe_version':'16.34.0','business_snapshot':{'counts':{'Student':121}}}))
        self.package=self.root/'copy.crmenc';self.key=self.root/'private.crmkey'
        pack(self.backup,self.snapshot,self.package,self.key)

    def tearDown(self):self.temp.cleanup()

    def test_roundtrip_and_source_db_password_excluded(self):
        out=self.root/'out';manifest=unpack(self.package,self.key,out)
        self.assertEqual(manifest['business_snapshot']['counts']['Student'],121)
        self.assertEqual(gzip.decompress((out/'database.sql.gz').read_bytes()),b'private fixture SQL')
        self.assertEqual(json.loads((out/'site-secrets.json').read_text()),{'encryption_key':'fixture-key'})
        self.assertNotIn(b'private fixture SQL',self.package.read_bytes())

    def test_wrong_key_does_not_extract(self):
        wrong=self.root/'wrong.crmkey';wrong.write_bytes(base64.urlsafe_b64encode(b'0'*32))
        with self.assertRaises(InvalidTag):unpack(self.package,wrong,self.root/'out')
        self.assertFalse((self.root/'out').exists())

    def test_tampered_ciphertext_does_not_extract(self):
        raw=bytearray(self.package.read_bytes());raw[-1]^=1;self.package.write_bytes(raw)
        with self.assertRaises(InvalidTag):unpack(self.package,self.key,self.root/'out')
        self.assertFalse((self.root/'out').exists())

    def test_existing_destinations_are_never_overwritten(self):
        out=self.root/'out';out.mkdir();(out/'keep').write_text('keep')
        with self.assertRaises(ValueError):unpack(self.package,self.key,out)
        with self.assertRaises(ValueError):pack(self.backup,self.snapshot,self.package,self.key)
        self.assertEqual((out/'keep').read_text(),'keep')


if __name__=='__main__':unittest.main()
