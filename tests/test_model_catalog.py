import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model_catalog import available_text_models
import providers
class ModelCatalogTests(unittest.TestCase):
 def test_4o_visible_legacy_removed(self):
  ids=['gpt-3.5-turbo','gpt-4o','gpt-4o-mini','gpt-4o-2024-05-13','gpt-4o-audio-preview','gpt-image-1','gpt-6.1-sol']
  self.assertEqual(available_text_models([{'id':m} for m in ids],today='2026-10-27'),['gpt-4o','gpt-4o-mini','gpt-6.1-sol'])
 def test_api_shutdown_date(self):
  self.assertEqual(available_text_models([{'id':'gpt-example','shutdown_date':'2026-10-27'},{'id':'gpt-future','shutdown_date':'2027-01-01'}],today='2026-10-27'),['gpt-future'])
 def test_retired_saved_model_fails_before_request(self):
  with patch.object(providers,'request_json') as request:
   with self.assertRaisesRegex(ValueError,'retiré'):providers.complete('test',{'provider':'openai','model':'gpt-3.5-turbo'})
  request.assert_not_called()
 def test_api_catalog_keeps_4o(self):
  with patch.object(providers,'secret',return_value='TEST'),patch.object(providers,'request_json',return_value={'data':[{'id':'gpt-4o'}]}):self.assertEqual(providers.models('openai'),['gpt-4o'])
