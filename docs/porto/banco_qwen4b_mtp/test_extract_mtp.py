"""CPU unit tests, including fail-closed Range handling; no external requests."""
import io, json, pathlib, struct, tempfile, unittest
from unittest.mock import patch
import extract_mtp as e

class Response:
 def __init__(self,status=206,cr='bytes 0-3/100',body=b'abcd',cl='4'):
  self.status=status;self.headers={'Content-Range':cr,'Content-Length':cl};self.body=body;self.reads=[]
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def read(self,n):self.reads.append(n);return self.body[:n]

class RangeTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.r=e.Remote(pathlib.Path(self.tmp.name),100)
 def tearDown(self):self.tmp.cleanup()
 def test_valid_range_and_cache_hash(self):
  response=Response()
  with patch('urllib.request.urlopen',return_value=response) as call:
   self.assertEqual(self.r.fetch(0,4),b'abcd');self.assertEqual(self.r.fetch(0,4),b'abcd');self.assertEqual(call.call_count,1)
  self.assertEqual(response.reads,[5]);self.assertEqual(self.r.records[0]['http_status'],206)
 def test_200_rejected_before_read(self):
  response=Response(status=200)
  with patch('urllib.request.urlopen',return_value=response),self.assertRaises(ValueError):self.r.fetch(0,4)
  self.assertEqual(response.reads,[])
 def test_content_range_rejected_before_read(self):
  response=Response(cr='bytes 1-4/100')
  with patch('urllib.request.urlopen',return_value=response),self.assertRaises(ValueError):self.r.fetch(0,4)
  self.assertEqual(response.reads,[])
 def test_content_length_rejected_before_read(self):
  response=Response(cl='100')
  with patch('urllib.request.urlopen',return_value=response),self.assertRaises(ValueError):self.r.fetch(0,4)
  self.assertEqual(response.reads,[])
 def test_oversized_response_rejected(self):
  with patch('urllib.request.urlopen',return_value=Response(body=b'abcde')),self.assertRaises(ValueError):self.r.fetch(0,4)
 def test_short_response_rejected(self):
  with patch('urllib.request.urlopen',return_value=Response(body=b'abc')),self.assertRaises(ValueError):self.r.fetch(0,4)
 def test_bad_cache_rejected(self):
  with patch('urllib.request.urlopen',return_value=Response()):self.r.fetch(0,4)
  next(pathlib.Path(self.tmp.name).glob('*.bin')).write_bytes(b'xxxx')
  with self.assertRaises(ValueError):self.r.fetch(0,4)
 def test_range_bound_without_network(self):
  with patch('urllib.request.urlopen') as call,self.assertRaises(ValueError):self.r.fetch(99,4)
  call.assert_not_called()
 def test_header_cap_without_network(self):
  self.r.seek(e.MAX_HEADER)
  with patch('urllib.request.urlopen') as call,self.assertRaises(ValueError):self.r.read(1)
  call.assert_not_called()

class GGUFTests(unittest.TestCase):
 def test_tensor_bytes(self):
  self.assertEqual(e.nbytes({'shape':[2560,248320],'type':14}),521472000)
  self.assertEqual(e.nbytes({'shape':[2560,9216],'type':8}),25067520)
  self.assertEqual(e.nbytes({'shape':[2560],'type':0}),10240)
 def test_unknown_quant_fails(self):
  with self.assertRaises(KeyError):e.nbytes({'shape':[2560],'type':99})
 def test_wrong_row_alignment(self):
  with self.assertRaises(ValueError):e.nbytes({'shape':[31,32],'type':8})
 def test_parse_roundtrip_metadata(self):
  fields=[e.modified('general.architecture',8,'qwen35'),e.modified('qwen35.block_count',4,33)]
  b=b'GGUF'+struct.pack('<IQQ',3,0,2)+b''.join(x['raw'] for x in fields)
  meta,tensors,base=e.parse(io.BytesIO(b))
  self.assertEqual(meta['qwen35.block_count']['value'],33);self.assertFalse(tensors);self.assertEqual(base%32,0)
 def test_bad_magic(self):
  with self.assertRaises(ValueError):e.parse(io.BytesIO(b'FAIL'))
 def test_bad_version(self):
  with self.assertRaises(ValueError):e.parse(io.BytesIO(b'GGUF'+struct.pack('<I',2)))

if __name__=='__main__':unittest.main(verbosity=2)
