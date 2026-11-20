"""Recheck known TWS Weverse MC notices; does not discover new notices."""
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse


class Description(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.value = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name') == 'description':
            self.value = attrs.get('content')


def extract_mc(event, html):
    source = urlparse(event.get('source_url', ''))
    if source.netloc != 'weverse.io' or not re.fullmatch(r'/tws/notice/\d+', source.path):
        return None
    if '人气歌谣' in event['title'] and any(n in event['title'] for n in ('申惟', 'SHINYU')):
        header = r'SBS\s*인기가요\s*[-–]\s*MC\s*신유'
    elif '音乐中心' in event['title'] and any(n in event['title'] for n in ('道勋', 'DOHOON')):
        header = r'MBC\s*쇼!\s*음악중심\s*[-–]\s*MC\s*도훈'
    else:
        return None
    p = Description()
    p.feed(html)
    if not p.value:
        raise ValueError('Weverse notice body unavailable')
    # Match the actual broadcast field, never the fan check-in/application times.
    match = re.search(r'\[' + header + r'\]\s*방송\s*일시\s*[:：]\s*'
                      r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(?:\([^)]*\))?\s*'
                      r'(\d{1,2})\s*[:：]\s*(\d{2})\s*(AM|PM)?', p.value, re.I)
    if not match:
        raise ValueError('Weverse MC broadcast time requires review')
    y, m, d, h, minute = map(int, match.group(1, 2, 3, 4, 5))
    ampm = (match.group(6) or '').upper()
    if h <= 12 and ampm == 'PM' and h != 12: h += 12
    if h == 12 and ampm == 'AM': h = 0
    return datetime(y, m, d, h, minute, tzinfo=timezone(timedelta(hours=9)))


def extract_video_fansign(event, html):
    """Read the event's own time field, never an application deadline."""
    source = urlparse(event.get('source_url', ''))
    if source.netloc != 'weverse.io' or not re.fullmatch(r'/tws/notice/\d+', source.path):
        return None
    if '签售' not in event['title'] or not any(x in event['title'] for x in ('视频', '线上', '影通')):
        return None
    p = Description(); p.feed(html)
    if not p.value:
        raise ValueError('Weverse notice body unavailable')
    matches = re.findall(r'\[영상통화\s*팬\s*사인회\]\s*[-–]?\s*일시\s*[:：]\s*'
                         r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(?:\([^)]*\))?\s*'
                         r'(\d{1,2})\s*[:：]\s*(\d{2})\s*(AM|PM)?\s*\(KST\)', p.value, re.I)
    if len(matches) != 1:
        raise ValueError('Weverse video fansign event time requires review')
    y, m, d, h, minute = map(int, matches[0][:5])
    ampm = matches[0][5].upper()
    if h < 12 and ampm == 'PM': h += 12
    if h == 12 and ampm == 'AM': h = 0
    return datetime(y, m, d, h, minute, tzinfo=timezone(timedelta(hours=9)))

