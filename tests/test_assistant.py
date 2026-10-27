import io,json,hashlib,tempfile,unittest,sys,zipfile
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import assistant,services,voice,updater,desktop

class AssistantTests(unittest.TestCase):
 def setUp(self):self.a=assistant.Assistant()
 def test_routes_french_and_accents(self):
  cases={'Check mes mails':'mail','Peux-tu résumer mes courriels ?':'mail','Rédige une interpellation sur les écoles':'draft','Fais une veille sur le logement':'watch','Mon agenda':'calendar','Désactive la veille automatique':'unschedule','Envoie ce mail':'send','Bonjour':'chat'}
  for q,action in cases.items():self.assertEqual(self.a.route(q),action,q)
 def test_mail_runs_real_service(self):
  with patch.object(services,'accounts',return_value={'pro':{}}),patch.object(services,'mail_summary',return_value={'text':'5 mails'}) as m:
   r=self.a.turn({'query':'Check mes mails'});m.assert_called_once_with({'account':'pro'});self.assertTrue(r['private']);self.assertTrue(self.a.private)
 def test_account_selection(self):
  with patch.object(services,'accounts',return_value={'pro':{},'perso':{}}),patch.object(services,'mail_summary',return_value={'text':'mails'}) as m:
   r=self.a.turn({'query':'Check mes mails'});self.assertEqual(r['choices'],['pro','perso']);m.assert_not_called()
   self.a.turn({'query':'perso'});m.assert_called_once_with({'account':'perso'})
 def test_missing_account_opens_settings(self):
  with patch.object(services,'accounts',return_value={}):self.assertEqual(self.a.turn({'query':'Lis mes mails'})['navigate'],'settings')
 def test_topic_followup(self):
  with patch('templates.catalog',return_value={'active':'t'}),patch.object(services,'chat',return_value={'text':'projet'}) as m:
   self.assertIn('quel sujet',self.a.turn({'query':'Rédige une interpellation'})['text'])
   self.a.turn({'query':'le logement à Bruxelles'});self.assertIn('logement',m.call_args.args[0]['query'])
 def test_draft_requires_template(self):
  with patch('templates.catalog',return_value={'active':''}),patch.object(services,'chat') as m:
   self.assertEqual(self.a.turn({'query':'Interpellation sur les écoles'})['navigate'],'templates');m.assert_not_called()
 def test_private_turn_cannot_start_public_search(self):
  with patch.object(services,'chat') as m:
   self.a.turn({'query':'Veille sur mon dossier privé','private':True});m.assert_not_called()
 def test_mail_history_cannot_leak_to_web(self):
  self.a.private=True
  with patch.object(services,'chat') as m:self.a.turn({'query':'Veille sur le logement'});m.assert_not_called()
 def test_confirm_once_and_cancel(self):
  with patch.object(services,'save_settings',return_value={'text':'OK'}) as m:
   r=self.a.turn({'query':'Veille quotidienne sur le logement à 08:30'});m.assert_not_called()
   self.a.confirm({'token':r['confirmation']});self.assertEqual(m.call_args.args[0],{'themes':'le logement','briefing_time':'08:30','schedule_enabled':True})
   with self.assertRaises(ValueError):self.a.confirm({'token':r['confirmation']})
   r=self.a.turn({'query':'Désactive la veille'});self.a.turn({'query':'annuler'})
   with self.assertRaises(ValueError):self.a.confirm({'token':r['confirmation']})
 def test_new_request_invalidates_confirmation(self):
  r=self.a.turn({'query':'Désactive la veille'})
  with patch.object(services,'diagnosis',return_value={'text':'OK'}):self.a.turn({'query':'Diagnostic'})
  with self.assertRaises(ValueError):self.a.confirm({'token':r['confirmation']})
 def test_send_only_opens_preview(self):
  with patch.object(desktop,'smtp_send') as send:
   r=self.a.turn({'query':'Envoie un mail à mon collègue'});self.assertEqual(r['focus'],'smtpCard');send.assert_not_called()
 def test_empty_and_concurrent_requests(self):
  with self.assertRaises(ValueError):self.a.turn({'query':''})
  self.a.lock.acquire()
  try:
   with self.assertRaises(ValueError):self.a.turn({'query':'bonjour'})
  finally:self.a.lock.release()
 def test_free_chat_keeps_context_and_privacy(self):
  self.a.private=True;self.a.history=[{'role':'user','text':'secret','private':True}]
  with patch.object(services,'complete',return_value={'text':'réponse'}) as m:
   self.a.turn({'query':'Explique davantage'});self.assertTrue(m.call_args.kwargs['private']);self.assertIn('secret',m.call_args.args[0]);self.a.reset();self.assertFalse(self.a.private)

class UpdateTests(unittest.TestCase):
 def manifest(self,**kwargs):return {'version':'3.1.0','url':updater.PREFIX+'Jarvis-Parlement-3.1.0-macOS.zip','sha256':'a'*64,**kwargs}
 def response(self,m):return patch.object(updater.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(m).encode()))
 def test_update_versions(self):
  with self.response(self.manifest()):self.assertTrue(updater.check()['available'])
  with self.response(self.manifest(version='3.0.0',url=updater.PREFIX+'Jarvis-Parlement-3.0.0-macOS.zip')):self.assertFalse(updater.check()['available'])
 def test_reject_remote_host_and_bad_hash(self):
  for m in [self.manifest(url='https://evil.example/a.zip'),self.manifest(sha256='bad'),self.manifest(version='x')]:
   with self.response(m),self.assertRaises(ValueError):updater.check()
 def test_checksum_mismatch_leaves_no_file(self):
  with tempfile.TemporaryDirectory() as d,patch.object(voice.urllib.request,'urlopen',return_value=io.BytesIO(b'bad')):
   target=Path(d)/'x'
   with self.assertRaises(ValueError):voice.checked_download('https://example.org',target,'0'*64)
   self.assertFalse(target.exists());self.assertEqual(list(Path(d).iterdir()),[])
 def test_extract_rejects_traversal(self):
  with tempfile.TemporaryDirectory() as d,patch.object(updater,'HOME',Path(d)),patch.object(updater,'check',return_value={**self.manifest(),'available':True}),patch.object(updater.subprocess,'run') as run:
   def download(url,target,digest,**kw):
    with zipfile.ZipFile(target,'w') as z:z.writestr('../escape','oops')
   with patch.object(updater,'checked_download',side_effect=download),self.assertRaises(ValueError):updater.install()
   run.assert_not_called()
 def test_valid_update_opens_installer(self):
  with tempfile.TemporaryDirectory() as d,patch.object(updater,'HOME',Path(d)),patch.object(updater,'check',return_value={**self.manifest(),'available':True}),patch.object(updater.subprocess,'run') as run:
   def download(url,target,digest,**kw):
    with zipfile.ZipFile(target,'w') as z:
     info=zipfile.ZipInfo('Installer Jarvis Parlement.app/Contents/MacOS/Installer');info.external_attr=0o100755<<16;z.writestr(info,'#!/bin/bash')
   with patch.object(updater,'checked_download',side_effect=download):r=updater.install()
   self.assertIn('Quitte Jarvis',r['text']);self.assertEqual(run.call_args.args[0][0],'open')

class VoiceTests(unittest.TestCase):
 def test_invalid_voice_no_process(self):
  with patch.object(voice.subprocess,'Popen') as p,self.assertRaises(ValueError):voice.Voice().speak({'text':'test','voice':'../../x'})
  p.assert_not_called()
 def test_missing_assets_helpful_error(self):
  with tempfile.TemporaryDirectory() as d,patch.object(voice,'CONFIG',Path(d)):
   v=voice.Voice()
   self.assertFalse(v.state()['installed'])
   with self.assertRaisesRegex(ValueError,'Installe'):v.listen()
   with self.assertRaisesRegex(ValueError,'Installe'):v.speak({'text':'Bonjour'})
 def test_microphone_is_off_at_launch(self):
  v=voice.Voice();self.assertFalse(v.state()['listening']);self.assertFalse(v.state()['speaking']);v.stop()

if __name__=='__main__':unittest.main()

class PlannerTests(unittest.TestCase):
 def test_paraphrase_planner_is_allowlisted(self):
  a=assistant.Assistant()
  with patch.object(assistant,'settings',return_value={'provider':'ollama','model':'test'}),patch.object(services,'complete',return_value={'text':'{"action":"mail","query":"Lis mes mails"}'}),patch.object(services,'accounts',return_value={'pro':{}}),patch.object(services,'mail_summary',return_value={'text':'résumé'}) as m:
   a.turn({'query':'Y a-t-il du nouveau dans ma messagerie ?'});m.assert_called_once()
 def test_invalid_planner_cannot_execute_code(self):
  a=assistant.Assistant()
  for output in ['{"action":"shell","query":"rm -rf /"}','not json','[]']:
   with patch.object(assistant,'settings',return_value={'provider':'ollama','model':'test'}),patch.object(services,'complete',return_value={'text':output}):self.assertEqual(a.interpret('test')[0],'chat')
 def test_private_schedule_blocked(self):
  a=assistant.Assistant()
  with patch.object(services,'save_settings') as s:
   r=a.turn({'query':'Veille quotidienne sur mon dossier à 08:30','private':True});self.assertNotIn('confirmation',r);s.assert_not_called()
 def test_explanations_and_negation_do_not_read_mail(self):
  a=assistant.Assistant()
  self.assertEqual(a.route('Ne lis pas mes mails'),'chat');self.assertEqual(a.route('Comment lire mes mails ?'),'chat')
