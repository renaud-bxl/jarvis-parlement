import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import desktop
from diagnostics import failure

class ModelSelectionTests(unittest.TestCase):
 def test_unsaved_selection_is_tested_without_saving(self):
  saved={'provider':'chatgpt','model':'old-model'}
  with patch.object(desktop,'settings',return_value=saved),patch.object(desktop.providers,'complete',return_value={'text':'Jarvis est prêt.'}) as complete:
   r=desktop.Api().call('test_ai',{'provider':'ollama','model':'local-test'})
  self.assertTrue(r['ok']);self.assertEqual(complete.call_args.args[1],{'provider':'ollama','model':'local-test'});self.assertEqual(saved['model'],'old-model')
 def test_empty_selection_does_not_test_old_model(self):
  with patch.object(desktop,'settings',return_value={'provider':'chatgpt','model':'old-model'}),patch.object(desktop.providers,'complete') as complete:
   r=desktop.Api().call('test_ai',{'provider':'chatgpt','model':''})
  self.assertFalse(r['ok']);complete.assert_not_called()
 def test_invalid_provider_rejected(self):
  with patch.object(desktop.providers,'complete') as complete:
   r=desktop.Api().call('test_ai',{'provider':'unknown','model':'test'})
  self.assertFalse(r['ok']);complete.assert_not_called()
 def test_diagnostic_reports_selected_model(self):
  def fail(prompt,cfg,**kw):raise failure('ChatGPT','generation',model=cfg['model'],fallback='unsupported_model')
  with patch.object(desktop.providers,'complete',side_effect=fail),patch.object(desktop.diagnostics,'record'):
   r=desktop.Api().call('test_ai',{'provider':'chatgpt','model':'selected-model'})
  self.assertEqual(r['diagnostic']['model'],'selected-model')
