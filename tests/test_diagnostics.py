import io,json,sys,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import chatgpt_auth,diagnostics,desktop,providers
class Reply(io.BytesIO):
 def __init__(self,content):super().__init__(content);self.headers={'x-request-id':'req_test123'}
class DiagnosticsTests(unittest.TestCase):
 def run_event(self,event,ending='\n\n'):
  raw=('data: '+json.dumps(event)+ending).encode()
  with patch.object(chatgpt_auth,'access_token',return_value='SECRET_TOKEN'),patch.object(chatgpt_auth.urllib.request,'urlopen',return_value=Reply(raw)):
   return chatgpt_auth.response({'model':'test-model','input':'SECRET_PROMPT'})
 def test_failed_quota_reason_retained(self):
  with self.assertRaises(diagnostics.ProviderError) as e:self.run_event({'type':'response.failed','response':{'error':{'code':'usage_limit_reached','message':'SECRET_TOKEN SECRET_PROMPT'}}})
  d=e.exception.diagnostic;self.assertEqual(d['code'],'usage_limit_reached');self.assertEqual(d['event'],'response.failed');self.assertEqual(d['request_id'],'req_test123');self.assertNotIn('SECRET',json.dumps(d))
 def test_incomplete_output_is_not_quota(self):
  with self.assertRaises(diagnostics.ProviderError) as e:self.run_event({'type':'response.incomplete','response':{'incomplete_details':{'reason':'max_output_tokens'}}})
  self.assertEqual(e.exception.diagnostic['code'],'max_output_tokens');self.assertNotIn('forfait',str(e.exception))
 def test_top_level_error_parameter(self):
  with self.assertRaises(diagnostics.ProviderError) as e:self.run_event({'type':'error','code':'unsupported_parameter','param':'tool_choice','message':'private'})
  self.assertEqual(e.exception.diagnostic['parameter'],'tool_choice')
 def test_complete_without_final_blank_line(self):
  r=self.run_event({'type':'response.completed','response':{'status':'completed','output':[]}},ending='')
  self.assertEqual(r['status'],'completed')
 def test_done_is_not_complete(self):
  with patch.object(chatgpt_auth,'access_token',return_value='secret'),patch.object(chatgpt_auth.urllib.request,'urlopen',return_value=Reply(b'data: [DONE]\n\n')),self.assertRaises(diagnostics.ProviderError) as e:chatgpt_auth.response({'model':'test'})
  self.assertEqual(e.exception.diagnostic['code'],'stream_interrupted')
 def test_http_status_and_code_survive(self):
  err=urllib.error.HTTPError('https://api.openai.com/v1/responses',401,'Unauthorized',{'x-request-id':'req_auth'},io.BytesIO(b'{"error":{"code":"invalid_token","message":"secret"}}'))
  with patch.object(chatgpt_auth,'access_token',return_value='secret'),patch.object(chatgpt_auth.urllib.request,'urlopen',side_effect=err),self.assertRaises(diagnostics.ProviderError) as e:chatgpt_auth.response({'model':'test'})
  self.assertEqual(e.exception.diagnostic['http_status'],401);self.assertEqual(e.exception.diagnostic['code'],'invalid_token')
 def test_unknown_code_does_not_invent_cause(self):
  d=diagnostics.failure('ChatGPT','generation',{'error':{'code':'future_error','message':'Your password is SECRET'}}).diagnostic
  self.assertEqual(d['code'],'future_error');self.assertIn('ne connaît pas',d['cause']);self.assertNotIn('SECRET',json.dumps(d))
 def test_unsafe_metadata_filtered(self):
  d=diagnostics.failure('ChatGPT','generation',{'error':{'code':'sk-SECRET','param':'SECRET'}},request_id='Bearer SECRET',model='private text').diagnostic
  self.assertNotIn('SECRET',json.dumps(d));self.assertNotIn('model',d)
 def test_bridge_persists_only_safe_diagnostic(self):
  with tempfile.TemporaryDirectory() as d,patch.object(diagnostics,'CONFIG',Path(d)),patch.object(providers,'complete',side_effect=diagnostics.failure('ChatGPT','generation',{'code':'model_not_found','message':'SECRET'})):
   api=desktop.Api();result=api.call('test_ai');self.assertFalse(result['ok']);self.assertEqual(result['diagnostic']['code'],'model_not_found');self.assertNotIn('SECRET',(Path(d)/'last-provider-error.json').read_text());self.assertEqual(api.call('diagnostic_last')['data']['code'],'model_not_found')
 def test_malformed_stream_has_explicit_cause(self):
  with patch.object(chatgpt_auth,'access_token',return_value='secret'),patch.object(chatgpt_auth.urllib.request,'urlopen',return_value=Reply(b'data: malformed\n\n')),self.assertRaises(diagnostics.ProviderError) as e:chatgpt_auth.response({'model':'test'})
  self.assertEqual(e.exception.diagnostic['code'],'invalid_stream')
 def test_oauth_error_is_distinct_from_generation(self):
  err=urllib.error.HTTPError('https://auth.openai.com/test',400,'Bad Request',{},io.BytesIO(b'{"error":"invalid_grant"}'))
  with patch.object(chatgpt_auth.urllib.request,'urlopen',side_effect=err),self.assertRaises(diagnostics.ProviderError) as e:chatgpt_auth._json('https://auth.openai.com/test')
  self.assertEqual(e.exception.diagnostic['stage'],'authorization');self.assertEqual(e.exception.diagnostic['code'],'invalid_grant')
 def test_provider_api_error_retains_status(self):
  err=urllib.error.HTTPError('https://api.openai.com/test',429,'Limit',{},io.BytesIO(b'{"error":{"code":"rate_limit_exceeded"}}'))
  with patch.object(providers.urllib.request,'urlopen',side_effect=err),self.assertRaises(diagnostics.ProviderError) as e:providers.request_json('https://api.openai.com/test')
  self.assertEqual(e.exception.diagnostic['code'],'rate_limit_exceeded');self.assertEqual(e.exception.diagnostic['http_status'],429)
