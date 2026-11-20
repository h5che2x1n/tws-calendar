"""Conservative reader for the public TWS Japan schedule, not arbitrary news."""
import re
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

BASE = 'https://tws-official.jp'
TZ = timezone(timedelta(hours=9))


class Listing(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_item = False
        self.collect = None
        self.bits = []
        self.fields = []
        self.href = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get('class', '').split()
        if tag == 'div' and 'news__container' in classes:
            self.in_item, self.fields, self.href = True, [], None
        elif self.in_item and ((tag == 'p' and 'news__text' in classes) or
                               (tag == 'a' and 'news__title' in classes)):
            self.collect, self.bits = tag, []
            if tag == 'a':
                self.href = urljoin(BASE, a.get('href', '')).split('?', 1)[0]

    def handle_data(self, data):
        if self.collect:
            self.bits.append(data)

    def handle_endtag(self, tag):
        if self.collect == tag:
            self.fields.append(' '.join(''.join(self.bits).split()))
            if tag == 'a':
                if len(self.fields) < 4 or not self.href:
                    raise ValueError('Japan schedule entry is missing fields')
                if urlparse(self.href).netloc != 'tws-official.jp' or not re.fullmatch(r'/schedule/[a-zA-Z0-9]+', urlparse(self.href).path):
                    raise ValueError('unexpected Japan schedule link')
                self.rows.append({'date': date.fromisoformat(self.fields[0].replace('.', '-')),
                                  'kind': self.fields[2], 'title': self.fields[-1], 'url': self.href})
                self.in_item = False
            self.collect = None


class Detail(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if not self.depth and dict(attrs).get('id') == 'news-desc':
            self.depth = 1
        elif self.depth and tag not in ('br', 'img', 'input', 'hr', 'meta', 'link'):
            self.depth += 1
        if self.depth and tag in ('div', 'p', 'li', 'br'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if self.depth and tag not in ('br', 'img', 'input', 'hr', 'meta', 'link'):
            self.depth -= 1
            if tag in ('div', 'p', 'li'):
                self.parts.append('\n')

    def handle_data(self, text):
        if self.depth:
            self.parts.append(text)

    def text(self):
        return '\n'.join(' '.join(line.split()) for line in ''.join(self.parts).splitlines() if line.strip())


def clock(day, hh, mm):
    hour, minute = int(hh), int(mm)
    if hour > 29 or minute > 59:
        raise ValueError('invalid Japan broadcast time')
    return datetime.combine(day, time(hour % 24, minute), TZ) + timedelta(days=hour // 24)


def extract(row, body):
    """Return a verified single broadcast or a reason for manual review."""
    if row['kind'] not in ('TV', 'RADIO'):
        return None, 'unsupported category'
    if re.search(r'中止|延期|変更のお知らせ|放送休止', row['title'] + body):
        return None, 'cancellation or change requires review'
    if re.search(r'SHINYU|DOHOON|YOUNGJAE|HANJIN|JIHOON|KYUNGMIN|シニュ|ドフン|ヨンジェ|ハンジン|ジフン|ギョンミン|신유|도훈|영재|한진|지훈|경민|一部メンバー|ソロ|ユニット', row['title'] + ' ' + body, re.I):
        return None, 'member participation requires review'
    lines = [x for x in body.splitlines() if '放送日時' in x or '放送日程' in x]
    if len(lines) != 1:
        return None, 'single broadcast time not found'
    line = lines[0]
    if re.search(r'毎週|毎日|毎月|曜日ごと', line):
        return None, 'recurring broadcasts require review'
    # Reject multi-date broadcasts; separate episodes need distinct identities.
    dates = re.findall(r'(?:(\d{4})年)?\s*(\d{1,2})月\s*(\d{1,2})日', line)
    if len(dates) != 1:
        return None, 'multiple or missing broadcast dates'
    year, month, day = dates[0]
    stated = date(int(year or row['date'].year), int(month), int(day))
    if stated != row['date']:
        return None, 'listing date differs from broadcast date'
    after = line.split('日', 1)[1]
    times = re.findall(r'(?<!\d)(\d{1,2})\s*[:：]\s*(\d{2})', after)
    if not 1 <= len(times) <= 2:
        return None, 'single broadcast time or range not found'
    if len(times) == 2 and not re.search(r'[～〜~–-]', after):
        return None, 'ambiguous broadcast time range'
    start = clock(stated, *times[0])
    event = {'id': 'jp-' + row['url'].rsplit('/', 1)[-1],
             'title': ('📺 ' if row['kind'] == 'TV' else '📻 ') + 'TWS｜' + row['title'],
             'status': 'confirmed', 'all_day': False, 'start': start.isoformat(),
             'location': '', 'details': 'TWS 节目出演。', 'source_url': row['url'],
             'duration_category': 'variety' if row['kind'] == 'TV' else 'radio'}
    if len(times) == 2:
        end = clock(stated, *times[1])
        if end <= start:
            # An end like 00:30 after 23:30 is next day, not a new guessed time.
            end += timedelta(days=1)
        if end - start > timedelta(hours=12):
            return None, 'implausible broadcast duration'
        event['end'] = end.isoformat()
    return event, None

