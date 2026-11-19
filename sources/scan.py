"""Collect links for human review, never create calendar events from page guesses."""
import json
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

SOURCES = {
    'japan': ('https://tws-official.jp/schedule', '/schedule/'),
    'pledis': ('https://www.pledis.co.kr/ko/artist/detail/TWS/notice/', '/artist/detail/TWS/notice/'),
}
AGENT = 'TWSCalendarBot/1.0'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.label = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.label = []

    def handle_data(self, data):
        if self.href is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            self.links.append((self.href, ' '.join(''.join(self.label).split())))
            self.href = None


def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': AGENT}), timeout=25) as response:
        if response.geturl().split('/')[2] != urlparse(url).netloc:
            raise ValueError('unexpected redirect host')
        return response.read(2_000_001)


def scan(name):
    url, path_prefix = SOURCES[name]
    parsed = urlparse(url)
    robots_url = f'{parsed.scheme}://{parsed.netloc}/robots.txt'
    robots = RobotFileParser()
    robots.parse(fetch(robots_url).decode('utf-8').splitlines())
    if not robots.can_fetch(AGENT, url):
        raise ValueError('robots.txt does not permit this URL')
    body = fetch(url)
    if len(body) > 2_000_000:
        raise ValueError('page too large')
    parser = Links()
    parser.feed(body.decode('utf-8'))
    found = {}
    for href, title in parser.links:
        full = urljoin(url, href)
        u = urlparse(full)
        if u.scheme == 'https' and u.netloc == parsed.netloc and u.path.startswith(path_prefix) and u.path.rstrip('/') != parsed.path.rstrip('/') and title:
            found[u.scheme + '://' + u.netloc + u.path] = title
    if not found:
        raise ValueError('no recognizable article links; page may require scripting or changed')
    return [{'title': title, 'url': link} for link, title in found.items()]


def main():
    result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'sources': {}}
    failed = False
    for name in SOURCES:
        try:
            result['sources'][name] = {'status': 'review_required', 'links': scan(name)}
        except Exception as exc:
            failed = True
            result['sources'][name] = {'status': 'unavailable', 'error': str(exc)}
    with open('source-report.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())

