"""Conservative reader for the public TWS Japan schedule, not arbitrary news."""
import re
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

BASE = 'https://tws-official.jp'
TZ = timezone(timedelta(hours=9))


class Listing(HTMLParser):
    def __init__(self, section='schedule'):
        super().__init__(convert_charrefs=True)
        if section not in ('schedule', 'news'):
            raise ValueError('unsupported Japan listing')
        self.section = section
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
                if urlparse(self.href).netloc != 'tws-official.jp' or not re.fullmatch('/' + self.section + r'/[a-zA-Z0-9]+', urlparse(self.href).path):
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
    """Return a verified single broadcast or live event, or a review reason."""
    if row['kind'] not in ('TV', 'RADIO', 'EVENT & LIVE'):
        return None, 'unsupported category'
    if re.search(r'中止|延期|変更のお知らせ|放送休止', row['title'] + body):
        return None, 'cancellation or change requires review'
    if re.search(r'SHINYU|DOHOON|YOUNGJAE|HANJIN|JIHOON|KYUNGMIN|シニュ|ドフン|ヨンジェ|ハンジン|ジフン|ギョンミン|신유|도훈|영재|한진|지훈|경민|一部メンバー|ソロ|ユニット', row['title'] + ' ' + body, re.I):
        return None, 'member participation requires review'
    if row['kind'] == 'EVENT & LIVE':
        return extract_live(row, body)
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


def extract_live(row, body):
    title = row['title']
    if re.search(r'POP.?UP|STORE|グッズ|チケット|抽選|発売|販売|応募|お渡し|特典', title, re.I):
        return None, 'event may be a sale or promotion'
    if not re.search(r'LIVE|CONCERT|TOUR|SHOWCASE|FAN\s?MEETING|FESTIVAL|コンサート|ライブ|ファンミーティング', title, re.I):
        return None, 'live event type requires review'
    event_lines = [line for line in body.splitlines() if re.search(r'開演', line)]
    # Multiple performances need individual stable identities and explicit matching.
    if len(event_lines) != 1:
        return None, 'multiple or missing live showtimes'
    line = event_lines[0]
    dates = re.findall(r'(?:(\d{4})年)?\s*(\d{1,2})月\s*(\d{1,2})日', line)
    if len(dates) != 1:
        return None, 'live show date requires review'
    year, month, day = dates[0]
    stated = date(int(year or row['date'].year), int(month), int(day))
    if stated != row['date']:
        return None, 'listing date differs from live date'
    starts = re.findall(r'(?:開演\s*[:：]?\s*(\d{1,2})\s*[:：]\s*(\d{2})|'
                        r'(\d{1,2})\s*[:：]\s*(\d{2})\s*開演)', line)
    if len(starts) != 1:
        return None, 'live start time requires review'
    hh, mm, hh_before, mm_before = starts[0]
    start = clock(stated, hh or hh_before, mm or mm_before)
    if re.search(r'SHOWCASE|ミニライブ|めざまし', title, re.I):
        minutes = 60
    elif re.search(r'FESTIVAL', title, re.I):
        minutes = 240
    elif re.search(r'TOUR|CONCERT|FAN\s?MEETING|コンサート|ファンミーティング', title, re.I):
        minutes = 150
    else:
        minutes = 90
    event = {'id': 'jp-' + row['url'].rsplit('/', 1)[-1],
             'title': '🎤 TWS｜' + title, 'status': 'confirmed', 'all_day': False,
             'start': start.isoformat(), 'end': (start + timedelta(minutes=minutes)).isoformat(),
             'end_estimated': True, 'location': '', 'details': 'TWS 演出。',
             'source_url': row['url']}
    # Only attach a map when the announcement contains one specific street address.
    lines = body.splitlines()
    venues = []
    for i, item in enumerate(lines):
        match = re.match(r'^■会場\s*[:：]?\s*(.*)$', item)
        if match:
            value = match.group(1) or (lines[i + 1] if i + 1 < len(lines) else '')
            found = re.fullmatch(r'([^()（）\n]+)[(（]([^()（）\n]+)[)）]', value.strip())
            if found and re.search(r'(東京都|北海道|(?:京都|大阪)府|.{2,3}県)', found.group(2)) and re.search(r'\d', found.group(2)):
                venues.append((found.group(1).strip(), found.group(2).strip()))
    if len(venues) == 1:
        venue, address = venues[0]
        event['location'] = venue + ' · ' + address
        event['map_query'] = address
    return event, None

