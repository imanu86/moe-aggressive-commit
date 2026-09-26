import io
import json
import unittest
from unittest.mock import patch

import bench_http


class StreamTests(unittest.TestCase):
    def fake(self, chunks, done=True):
        data = ''.join('data: ' + json.dumps(c, ensure_ascii=False) + '\n\n' for c in chunks)
        if done:
            data += 'data: [DONE]\n\n'
        return io.BytesIO(data.encode('utf-8'))

    def test_fragmented_tools_and_usage(self):
        chunks = [
            {'choices': [{'delta': {'role': 'assistant'}}]},
            {'choices': [{'delta': {'reasoning_content': 'Controllo lo schema.'}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {
                'name': 'cgc_cockpit', 'arguments': '{"numbers":'}}]}}]},
            {'choices': [{'delta': {'tool_calls': [{'index': 0, 'function': {
                'arguments': '[1,2,3]}'}}]}, 'finish_reason': 'tool_calls'}]},
            {'choices': [], 'usage': {'completion_tokens': 42}, 'timings': {'predicted_per_second': 67}},
        ]
        with patch.object(bench_http, 'request', return_value=self.fake(chunks)):
            r = bench_http.stream('http://invalid', 'not-used', {})
        self.assertTrue(r['done'])
        self.assertEqual(r['finish'], 'tool_calls')
        self.assertEqual(r['tools'], [{'name': 'cgc_cockpit', 'arguments': '{"numbers":[1,2,3]}'}])
        self.assertEqual(r['usage']['completion_tokens'], 42)
        self.assertEqual(r['timings']['predicted_per_second'], 67)
        self.assertIsNone(r['first_text_s'])
        self.assertGreaterEqual(r['first_tool_s'], r['first_delta_s'])

    def test_unicode_and_incomplete_stream(self):
        chunks = [{'choices': [{'delta': {'content': 'È corretto'}}]}]
        with patch.object(bench_http, 'request', return_value=self.fake(chunks, False)):
            r = bench_http.stream('http://invalid', '', {})
        self.assertEqual(r['text'], 'È corretto')
        self.assertFalse(r['done'])
        self.assertIsNotNone(r['first_text_s'])

    def test_space_free_multiline_sse(self):
        payload = b'data:{"choices":\ndata:[{"delta":{"content":"OK"},"finish_reason":"stop"}]}\n\ndata:[DONE]\n\n'
        with patch.object(bench_http, 'request', return_value=io.BytesIO(payload)):
            result = bench_http.stream('http://invalid', '', {})
        self.assertTrue(result['done'])
        self.assertEqual(result['text'], 'OK')

    def test_stream_error_fails(self):
        with patch.object(bench_http, 'request', return_value=self.fake([{'error': 'bad'}])):
            with self.assertRaises(RuntimeError):
                bench_http.stream('http://invalid', '', {})

    def test_comparator_rejects_empty_missing_and_duplicate(self):
        import compare
        row = {'case': 'a', 'repeat': 0}
        for left, right in (([], []), ([row], []), ([row, row], [row]),
                            ([row], [dict(row, case='b')])):
            with self.assertRaises(ValueError):
                compare.compare(left, right)

    def test_multi_turn_uses_tool_history_and_cache(self):
        import tempfile
        from pathlib import Path
        from contextlib import redirect_stdout
        captured = []
        def fake_stream(url, key, payload):
            captured.append(payload)
            return {'seconds': 1, 'first_delta_s': 0.1, 'first_text_s': None, 'first_tool_s': 0.1,
                    'done': True, 'finish': 'tool_calls', 'text': '', 'reasoning': '', 'logprobs': [],
                    'usage': {'prompt_tokens': 100}, 'timings': {},
                    'tools': [{'name': 'cgc_cockpit', 'arguments': json.dumps({
                        'mode': 'operation', 'operation': 'screen_text',
                        'arguments': {'numbers': [1, 2, 3], 'find': 'Saldo'}})}]}
        def fake_request(url, path, key, payload=None):
            obj = {'default_generation_settings': {'n_ctx': 131072}} if path == '/props' else {'data': []}
            return io.BytesIO(json.dumps(obj).encode())
        with tempfile.TemporaryDirectory() as directory:
            args = ['bench_http.py', '--label', 'unit', '--out', str(Path(directory) / 'run'),
                    '--case', 'tool_batch', '--repeats', '4', '--multi-turn']
            with patch('sys.argv', args), patch.object(bench_http, 'request', side_effect=fake_request), \
                 patch.object(bench_http, 'stream', side_effect=fake_stream), redirect_stdout(io.StringIO()):
                bench_http.main()
            self.assertEqual([len(b['messages']) for b in captured[1:]], [2, 5, 8, 11])
            self.assertTrue(all(b['cache_prompt'] for b in captured[1:]))
            self.assertEqual(captured[2]['messages'][2]['tool_calls'][0]['id'], 'simulated_0')
            self.assertEqual(captured[2]['messages'][3]['tool_call_id'], 'simulated_0')

    def test_hash_ignores_dictionary_order(self):
        self.assertEqual(bench_http.sha({'a': 1, 'b': 2}), bench_http.sha({'b': 2, 'a': 1}))


if __name__ == '__main__':
    unittest.main()
