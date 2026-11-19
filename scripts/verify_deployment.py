import os
import time
from urllib.request import Request, urlopen

expected = open('site/tws.ics', 'rb').read()
url = os.environ['PAGE_URL'].rstrip('/') + '/tws.ics'
for attempt in range(12):
    try:
        with urlopen(Request(url, headers={'Cache-Control': 'no-cache'}), timeout=15) as response:
            actual = response.read()
        if actual == expected:
            print('Verified deployed calendar:', url)
            break
        print('Published content not yet current')
    except Exception as exc:
        print('Waiting for calendar:', exc)
    time.sleep(10)
else:
    raise SystemExit('Public calendar did not match the generated file')

