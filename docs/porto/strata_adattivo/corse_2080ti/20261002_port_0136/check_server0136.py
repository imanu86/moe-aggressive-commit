from pathlib import Path
import os
import subprocess
import sys

R=Path(__file__).resolve().parent
env=dict(os.environ)
env.pop('STRATA_API_KEY',None)
code="import sys,runpy; sys.path.insert(0,r'D:\\ds4_work\\strata\\Strata\\.venv\\Lib\\site-packages'); sys.argv=['unittest','serve.test_server','-v']; runpy.run_module('unittest',run_name='__main__')"
with (R/'0136-server-tests.log').open('w',encoding='utf-8') as log:
    p=subprocess.run([sys.executable,'-B','-u','-X','utf8','-c',code],cwd=R/'candidate0136',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
print('Server mock tests exit',p.returncode)
print((R/'0136-server-tests.log').read_text(encoding='utf-8')[-3500:])
sys.exit(p.returncode)
