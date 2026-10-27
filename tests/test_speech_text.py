import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from speech_text import for_speech
import services

class SpeechTests(unittest.TestCase):
 def test_user_example(self):
  text=r'\### Sources & Points à Vérifier \* \*\*Canon URL :\*\* `[https://image.canon/st/fr/maintenance.html`](https://image.canon/st/fr/maintenance.html`)'
  spoken=for_speech(text)
  for forbidden in ['*','#','`','https://','maintenance.html','\\']:
   self.assertNotIn(forbidden,spoken)
 def test_link_label_and_french_preserved(self):
  self.assertEqual(for_speech('**Échéance** : [consulter le dossier](https://example.org/?secret=123).'),'Échéance : consulter le dossier.')
 def test_plain_text_preserved(self):
  self.assertEqual(for_speech('Bonjour. Nouveau mail, numéro 2. Répondre avant vendredi.'),'Bonjour. Nouveau mail, numéro 2. Répondre avant vendredi.')
 def test_separate_mail_announcements(self):
  messages=[{'from':'Canon <no-reply@example.com>','subject':'Maintenance','body':'TECHNICAL_A'}, {'from':'Marie <marie@example.com>','subject':'Réunion','body':'MEETING_B'}]
  with patch.object(services,'mail_read',return_value=messages),patch.object(services,'settings',return_value={'local_model':'test'}),patch.object(services,'complete',side_effect=[{'text':'**Maintenance demain.**'},{'text':'Réunion vendredi.'}]) as complete,patch.object(services,'save_result',side_effect=lambda r,t:r):
   result=services.mail_summary({'account':'demo'})
  self.assertEqual(result['text'].count('Nouveau mail, numéro'),2)
  self.assertIn('De : Canon. Objet : Maintenance.',result['text'])
  self.assertNotIn('MEETING_B',complete.call_args_list[0].args[0])
  self.assertNotIn('TECHNICAL_A',complete.call_args_list[1].args[0])
  for call in complete.call_args_list:
   self.assertFalse(call.kwargs['web']);self.assertTrue(call.kwargs['private']);self.assertEqual(call.args[1]['provider'],'ollama')
 def test_no_mail_no_inference(self):
  with patch.object(services,'mail_read',return_value=[]),patch.object(services,'settings',return_value={}),patch.object(services,'complete') as complete,patch.object(services,'save_result',side_effect=lambda r,t:r):
   result=services.mail_summary({})
  complete.assert_not_called();self.assertEqual(result['text'],'Aucun mail disponible.')
