"""Write fresh CPU test evidence as UTF-8 without BOM; never invoke GPU/runtime."""
import contextlib
import pathlib
import unittest
import test_extract_mtp
import verify_sidecar

lab=pathlib.Path(r'D:\ds4_work\qwen4b_mtp_lab')
with (lab/'cpu-unit-tests.utf8.txt').open('x',encoding='utf-8') as f:
 result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_extract_mtp))
 if not result.wasSuccessful():raise SystemExit(1)
with (lab/'independent-readback.utf8.json').open('x',encoding='utf-8') as f:
 with contextlib.redirect_stdout(f):verify_sidecar.main(lab/'manifest.json')
print('CPU tests and independent verification passed; UTF-8 evidence written.')
