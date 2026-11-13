import os
from pathlib import Path
roots=[Path('/init')/n for n in ['application','evidence','prospect','redis']]
if any(any(p.iterdir()) for p in roots):raise SystemExit('Refusing nonempty staging storage')
for p in roots:
 os.chown(p,999 if p.name=='redis' else 10001,999 if p.name=='redis' else 10001)
 os.chmod(p,0o700)
print('Fresh isolated staging volume ownership initialized')
