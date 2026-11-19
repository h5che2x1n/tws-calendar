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


def original_events(text):
    raw = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    unfolded = []
    for line in raw:
        if line.startswith((' ', '\t')):
            if not unfolded:
                raise ValueError('invalid folded line')
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    result, block = [], None
    for line in unfolded:
        if line == 'BEGIN:VEVENT':
            if block is not None:
                raise ValueError('nested event')
            block = [line]
        elif block is not None:
            block.append(line.replace('导入后不会自动更新。', '原始快照，后续变更需另行核查。'))
            if line == 'END:VEVENT':
                ids = [x[4:] for x in block if x.startswith('UID:')]
                if len(ids) != 1:
                    raise ValueError('original event must have one UID')
                result.append((ids[0], block))
                block = None
    if block is not None or not result:
        raise ValueError('invalid or empty original calendar')
    if len({uid for uid, _ in result}) != len(result):
        raise ValueError('duplicate original UID')
    return result


def build(events, original=None):
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
            start = timestamp(e['start'])
            end = timestamp(e['end']) if e.get('end') else None
            startline, endline = 'DTSTART:' + fmt(start), ('DTEND:' + fmt(end) if end else None)
        else:
            raise ValueError('all_day must be boolean')
        if end is not None and end <= start:
            raise ValueError('end must follow start')
        desc = e.get('details', e.get('description', ''))
        if e.get('time_tbd'):
            if not e['all_day']:
                raise ValueError('time_tbd requires date-only event')
            desc = '具体时间待公布（日期占位）\n' + desc
        desc += '\n官方公告: ' + e['source_url']
        if e.get('watch_url'):
            url = urlparse(e['watch_url'])
            if url.scheme != 'https' or not url.netloc:
                raise ValueError('watch_url must be HTTPS')
            desc += '\n观看链接: ' + e['watch_url']
        lines += ['BEGIN:VEVENT', 'UID:' + uid + '@tws-calendar', 'DTSTAMP:' + fmt(updated), 'LAST-MODIFIED:' + fmt(updated), 'SEQUENCE:' + str(e['sequence']), startline]
        if endline:
            lines.append(endline)
        if e.get('location'):
            lines.append('LOCATION:' + escape(e['location']))
        lines += ['SUMMARY:' + escape(e['title']), 'DESCRIPTION:' + escape(desc), 'URL:' + e['source_url'], 'STATUS:' + ('CANCELLED' if e['status'] == 'cancelled' else 'CONFIRMED'), 'END:VEVENT']
    if original is not None:
        for uid, block in original_events(original):
            if uid not in {item + '@tws-calendar' for item in seen}:
                lines.extend(block)
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(map(fold, lines)) + '\r\n').encode('utf-8')


if __name__ == '__main__':
    events = json.loads(Path('data/events.json').read_text(encoding='utf-8'))
    if not isinstance(events, list):
        raise ValueError('events must be an array')
    Path('site').mkdir(exist_ok=True)
    original = Path('data/original.ics').read_text(encoding='utf-8')
    Path('site/tws.ics').write_bytes(build(events, original))

