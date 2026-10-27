import sys,base64,unittest
from pathlib import Path
from email.message import EmailMessage
from email import policy
from email.parser import BytesParser
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import desktop,services
from mail_content import content,message_data
ACCOUNT={'type':'imap','address':'from@example.org'}
def file(name,data):return {'name':name,'content':base64.b64encode(data).decode()}
class MailFeaturesTests(unittest.TestCase):
 def test_html_only_render_and_summary(self):
  m=EmailMessage();m.set_content('<h2>Bonjour</h2><p>Réunion vendredi.</p>',subtype='html')
  c=content(m);self.assertIn('<h2>Bonjour</h2>',c['html']);self.assertIn('Réunion vendredi.',c['body']);self.assertNotIn('<p>',c['body'])
 def test_html_no_active_content_or_remote_requests(self):
  m=EmailMessage();m.set_content('<script>secret()</script><img src="https://tracker.test"><p onclick="attack()" style="color:red;background-image:url(https://tracker.test)">Bonjour</p><a href="javascript:attack()">Lire</a><input>Fin',subtype='html')
  c=content(m)
  for bad in ('<script','onclick','javascript:','https://','background-image','<input'):self.assertNotIn(bad,c['html'])
  self.assertIn('color:red',c['html']);self.assertIn('Fin',c['body'])
 def test_cid_embedded_image(self):
  m=EmailMessage();m.set_content('Texte');m.add_alternative('<img src="cid:logo">',subtype='html');m.get_payload()[1].add_related(b'fakepng',maintype='image',subtype='png',cid='<logo>')
  self.assertIn('data:image/png;base64,',content(m)['html'])
 def test_reply_metadata(self):
  m=EmailMessage();m['From']='Auteur <a@example.org>';m['Reply-To']='reply@example.org';m['Message-ID']='<id@example.org>';m.set_content('bonjour')
  d=message_data(m,'test');self.assertEqual(d['reply_to'],'reply@example.org');self.assertEqual(d['message_id'],'<id@example.org>')
 def test_composed_attachment_bytes_and_reply_headers(self):
  with patch.object(services,'accounts',return_value={'test':ACCOUNT}):
   _,_,raw,fields=desktop.mail_preview({'account':'test','to':'to@example.org','subject':'Re: Bonjour','body':'Réponse','in_reply_to':'<id@example.org>','references':'<id@example.org>','attachments':[file('dossier.pdf',b'%PDF-test')]})
  m=BytesParser(policy=policy.default).parsebytes(raw);self.assertEqual(m['In-Reply-To'],'<id@example.org>');self.assertEqual(next(m.iter_attachments()).get_payload(decode=True),b'%PDF-test');self.assertEqual(fields['attachments'],[{'name':'dossier.pdf','size':9}])
 def test_eml_existing_and_added_attachments(self):
  m=EmailMessage();m['From']='from@example.org';m['To']='to@example.org';m['Subject']='Sujet';m.set_content('<b>Corps HTML</b>',subtype='html');m.add_attachment(b'original',maintype='application',subtype='octet-stream',filename='original.bin')
  with patch.object(services,'accounts',return_value={'test':ACCOUNT}):
   _,_,raw,fields=desktop.mail_preview({'account':'test','file':file('mail.eml',m.as_bytes()),'attachments':[file('new.txt',b'new')]})
  parsed=BytesParser(policy=policy.default).parsebytes(raw);self.assertEqual([p.get_payload(decode=True) for p in parsed.iter_attachments()],[b'original',b'new']);self.assertIn('<b>Corps HTML</b>',fields['html'])
 def test_attachment_limit(self):
  m=EmailMessage();m.set_content('test')
  with self.assertRaises(ValueError):desktop.add_mail_attachments(m,[file('x',b'')]*21)
 def test_reply_header_injection_rejected(self):
  with patch.object(services,'accounts',return_value={'test':ACCOUNT}):
   with self.assertRaises(ValueError):desktop.mail_preview({'account':'test','to':'to@example.org','subject':'test','body':'test','in_reply_to':'<id>\r\nBcc: hidden@example.org'})
 def test_preview_attachment_snapshot_is_sent_once(self):
  data={'account':'test','to':'to@example.org','subject':'test','body':'test','attachments':[file('x.txt',b'approved')]}
  api=desktop.Api();api._window=Mock();api._window.create_confirmation_dialog.return_value=True
  with patch.object(services,'accounts',return_value={'test':ACCOUNT}),patch.object(desktop,'smtp_send',return_value={'text':'accepted'}) as send:
   result=api.call('mail_preview',data)['data'];data['attachments'][0]=file('x.txt',b'changed')
   api.call('mail_send',{'nonce':result['nonce']});raw=send.call_args.args[0][2];m=BytesParser(policy=policy.default).parsebytes(raw);self.assertEqual(next(m.iter_attachments()).get_payload(decode=True),b'approved');self.assertFalse(api.call('mail_send',{'nonce':result['nonce']})['ok'])
