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
            block.append(line)
            if line == 'END:VEVENT':
                ids = [x[4:] for x in block if x.startswith('UID:')]
                if len(ids) != 1:
                    raise ValueError('original event must have one UID')
                result.append((ids[0], clean_original(block)))
                block = None
    if block is not None or not result:
        raise ValueError('invalid or empty original calendar')
    if len({uid for uid, _ in result}) != len(result):
        raise ValueError('duplicate original UID')
    return result


def clean_original(block):
    """Keep the imported UID and timing, while removing research notes."""
    result = []
    title = next((x[len('SUMMARY:'):] for x in block if x.startswith('SUMMARY:')), '')
    concise = {
        '《Show! 音乐中心》预录': 'TWS《Show! 音乐中心》预录。',
        'TO US 官方快闪店最后一天': 'TWS《TO US》官方快闪店营业最后一天。',
        '《Show! 音乐中心》播出／DOHOON 特别MC': 'TWS 出演《Show! 音乐中心》，DOHOON 担任特别 MC。',
        '《做家务的男人们2》': 'JIHOON 出演《做家务的男人们2》。',
        '2026 KGMA Music Day': 'TWS 出演 2026 KGMA Music Day。',
        'MMA 2026 DAY 1': 'TWS 出演 MMA 2026 第一天。',
        'AAA 2026 DAY 2': 'TWS 出演 AAA 2026 第二天。',
        'M2U RECORD 线下签售': 'TWS《TO US》线下签售；具体会场另行通知。',
        '日本巡演全曲无删减电视首播': '2026 TWS 日本巡演全曲无删减版电视首播。',
    }
    for line in block:
        if line.startswith('DESCRIPTION:'):
            parts = line[len('DESCRIPTION:'):].split('\\n')
            intro = parts[0]
            for key, value in concise.items():
                if key in title:
                    intro = value
                    break
            if '生日' in title:
                intro = intro.split('；', 1)[0] + '。'
            intro = re.sub(r'；(?:[^。]*交叉参考|[^。]*未采用)[^。]*。', '。', intro)
            intro = re.sub(r'官方公告具体时间待通知；第三方20:00未采用。', '时间待公布。', intro)
            intro = re.sub(r'官网确认TWS为12月12日阵容；17:00 JST开演参考Soompi年末汇总。', 'TWS出演日本场第一天。', intro)
            intro = re.sub(r'典礼开始时间，不是TWS个人舞台时间。官网：[^；]*；', '', intro)
            intro = re.sub(r'时间参考：\S+', '', intro)
            intro = re.sub(r'；17:00为台湾当地典礼时间，与北京时间相同。时间参考Soompi年末汇总；非单独舞台时刻。', '出演12月6日。', intro)
            sources = [p for p in parts if p.startswith('来源：')]
            desc = '\\n'.join(filter(None, [intro.strip()] + sources))
            line = 'DESCRIPTION:' + desc
        elif line.startswith('LOCATION:'):
            value = line[len('LOCATION:'):]
            if value in ('线上', 'MBC', 'KBS 2TV', 'SBS', 'YouTube：KBS Kpop', 'TBS Channel 1'):
                line = 'LOCATION:'
        elif line.startswith('SEQUENCE:'):
            line = 'SEQUENCE:' + str(int(line.split(':', 1)[1]) + 1)
        elif line.startswith('DTSTAMP:'):
            line = 'DTSTAMP:20261119T124500Z'
        result.append(line)
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
        if e.get('end_estimated') and (e['all_day'] or end is None):
            raise ValueError('estimated end requires a timed event with end')
        desc = e.get('details', e.get('description', ''))
        if e.get('end_estimated'):
            desc += '\n结束时间为估计，实际以官方安排为准。'
        if e.get('time_tbd'):
            if not e['all_day']:
                raise ValueError('time_tbd requires date-only event')
            desc = '具体时间待公布（日期占位）\n' + desc
        if not e.get('historical'):
            desc += '\n官方公告: ' + e['source_url']
        if e.get('watch_url') and not e.get('historical'):
            url = urlparse(e['watch_url'])
            if url.scheme != 'https' or not url.netloc:
                raise ValueError('watch_url must be HTTPS')
        lines += ['BEGIN:VEVENT', 'UID:' + uid + '@tws-calendar', 'DTSTAMP:' + fmt(updated), 'LAST-MODIFIED:' + fmt(updated), 'SEQUENCE:' + str(e['sequence']), startline]
        if endline:
            lines.append(endline)
        location = e.get('location', '')
        if e.get('watch_url') and not e.get('historical') and e['watch_url'] not in location:
            location = '\n'.join(filter(None, (location, e['watch_url'])))
        if location:
            lines.append('LOCATION:' + escape(location))
        lines += ['SUMMARY:' + escape(e['title']), 'DESCRIPTION:' + escape(desc)]
        if not e.get('historical'):
            lines.append('URL:' + e['source_url'])
        lines.append('STATUS:' + ('CANCELLED' if e['status'] == 'cancelled' else 'CONFIRMED'))
        if e.get('remind_at_start'):
            if e['all_day']:
                raise ValueError('start reminder requires a confirmed time')
            if e['status'] != 'cancelled':
                lines += ['BEGIN:VALARM', 'TRIGGER:PT0S', 'ACTION:DISPLAY', 'DESCRIPTION:' + escape(e['title'] + ' 开始'), 'END:VALARM']
        lines.append('END:VEVENT')
    if original is not None:
        for uid, block in original_events(original):
            if uid not in {item + '@tws-calendar' for item in seen}:
                lines.extend(block)
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(map(fold, lines)) + '\r\n').encode('utf-8')


if __name__ == '__main__':
    events = json.loads(Path('data/events.json').read_text(encoding='utf-8'))
    events += json.loads(Path('data/history.json').read_text(encoding='utf-8'))
    if not isinstance(events, list):
        raise ValueError('events must be an array')
    Path('site').mkdir(exist_ok=True)
    original = Path('data/original.ics').read_text(encoding='utf-8')
    Path('site/tws.ics').write_bytes(build(events, original))

