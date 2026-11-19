import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def escape(value):
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold(line):
    chunks, chunk, limit = [], '', 75
    for char in line:
        if len((chunk + char).encode('utf-8')) > limit:
            chunks.append(chunk)
            chunk, limit = ' ', 75
        chunk += char
    chunks.append(chunk)
    return '\r\n'.join(chunks)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('datetime must include UTC offset')
    return parsed.astimezone(timezone.utc)


def fmt(value):
    return value.strftime('%Y%m%dT%H%M%SZ')


def build(events):
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//TWS Calendar//ZH', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:TWS 官方行程']
    seen = set()
    for e in events:
        uid = e['id']
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', uid) or uid in seen:
            raise ValueError('invalid or duplicate event id')
        seen.add(uid)
        if not e['title'].strip() or e['status'] not in ('confirmed', 'cancelled'):
            raise ValueError('invalid title or status')
        if not isinstance(e['sequence'], int) or isinstance(e['sequence'], bool) or e['sequence'] < 0:
            raise ValueError('invalid sequence')
        for key in ('source_url',):
            url = urlparse(e[key])
            if url.scheme != 'https' or not url.netloc:
                raise ValueError('source must be an HTTPS URL')
        updated = timestamp(e['updated_at'])
        if e['all_day'] is True:
            start, end = date.fromisoformat(e['start']), date.fromisoformat(e['end'])
            startline, endline = 'DTSTART;VALUE=DATE:' + start.strftime('%Y%m%d'), 'DTEND;VALUE=DATE:' + end.strftime('%Y%m%d')
        elif e['all_day'] is False:
            start, end = timestamp(e['start']), timestamp(e['end'])
            startline, endline = 'DTSTART:' + fmt(start), 'DTEND:' + fmt(end)
        else:
            raise ValueError('all_day must be boolean')
        if end <= start:
            raise ValueError('end must follow start')
        desc = e.get('description', '') + '\n官方公告: ' + e['source_url']
        if e.get('watch_url'):
            url = urlparse(e['watch_url'])
            if url.scheme != 'https' or not url.netloc:
                raise ValueError('watch_url must be HTTPS')
            desc += '\n观看链接: ' + e['watch_url']
        lines += ['BEGIN:VEVENT', 'UID:' + uid + '@tws-calendar', 'DTSTAMP:' + fmt(updated), 'LAST-MODIFIED:' + fmt(updated), 'SEQUENCE:' + str(e['sequence']), startline, endline, 'SUMMARY:' + escape(e['title']), 'DESCRIPTION:' + escape(desc), 'URL:' + e['source_url'], 'STATUS:' + ('CANCELLED' if e['status'] == 'cancelled' else 'CONFIRMED'), 'END:VEVENT']
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(map(fold, lines)) + '\r\n').encode('utf-8')


if __name__ == '__main__':
    events = json.loads(Path('data/events.json').read_text(encoding='utf-8'))
    if not isinstance(events, list):
        raise ValueError('events must be an array')
    Path('site').mkdir(exist_ok=True)
    Path('site/tws.ics').write_bytes(build(events))

