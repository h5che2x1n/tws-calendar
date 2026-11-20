import json
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, quote_plus
from venue_maps import map_location


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


DEFAULT_MINUTES = {'video_fansign': 60, 'offline_fansign': 120,
                   'year_end': 240, 'music_bank': 90, 'music_core': 80,
                   'inkigayo': 70, 'radio': 120, 'variety': 60}


def duration_category(title, explicit=None):
    if explicit is not None:
        if explicit not in DEFAULT_MINUTES:
            raise ValueError('unknown duration category')
        return explicit
    t = title.lower()
    if '预录' in t or '事前录制' in t:
        return None
    if any(x in t for x in ('签售', 'fansign', '팬사인회')):
        return 'video_fansign' if any(x in t for x in ('视频', '线上', 'video', 'online', '영상통화')) else 'offline_fansign'
    if any(x in t for x in ('music bank global', '歌谣大战', 'kgma', 'mma 2026', 'aaa 2026', 'asia artist awards', 'mama awards')):
        return 'year_end'
    if any(x in t for x in ('music bank', '音乐银行', '뮤직뱅크')): return 'music_bank'
    if any(x in t for x in ('音乐中心', 'music core', '음악중심')): return 'music_core'
    if any(x in t for x in ('人气歌谣', 'inkigayo', '인기가요')): return 'inkigayo'
    if any(x in t for x in ('radio', '电台', '라디오')): return 'radio'
    if any(x in t for x in ('偶像两天一夜', '돌박이일', 'tws tours in bangkok', '做家务的男人们')): return 'variety'
    return None


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
        if line.startswith('URL:') or (line.startswith('DESCRIPTION:') and '生日' in title):
            continue
        if line.startswith('SUMMARY:'):
            if '生日' in title: icon = '🎂 '
            elif any(x in title for x in ('签售', '合影')): icon = '🤝 '
            elif any(x in title for x in ('KGMA', 'MMA', 'AAA', 'Festival', '歌谣大战')): icon = '🏆 '
            elif 'VR' in title or '快闪店' in title: icon = '🎬 '
            else: icon = '📺 '
            line = 'SUMMARY:' + icon + title
        elif line.startswith('DESCRIPTION:'):
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
            if value in ('线上', 'MBC', 'KBS 2TV', 'SBS', 'YouTube：KBS Kpop', 'TBS Channel 1') or '仅通知' in value or '通知中签者' in value:
                line = 'LOCATION:'
            if '播出／DOHOON 特别MC' in title:
                line = 'LOCATION:https://onair.imbc.com/'
            elif '《人气歌谣》／SHINYU MC' in title:
                line = 'LOCATION:https://www.sbs.co.kr/live'
            elif '做家务的男人们2' in title:
                line = 'LOCATION:https://onair.kbs.co.kr/index.html?ch_code=12&ch_type=globalList&sname=onair&stype=live'
            if line == 'LOCATION:首尔 高尺天空巨蛋':
                line = 'LOCATION:' + escape(map_location('首尔 高尺天空巨蛋'))
            elif line.startswith('LOCATION:'):
                value = line[len('LOCATION:'):]
                mapped = map_location(value)
                if mapped != value:
                    line = 'LOCATION:' + escape(mapped)
        elif line.startswith('SEQUENCE:'):
            line = 'SEQUENCE:' + str(int(line.split(':', 1)[1]) + 6)
        elif line.startswith('DTSTAMP:'):
            line = 'DTSTAMP:20261119T145500Z'
        result.append(line)
    starts = [x for x in result if x.startswith('DTSTART:')]
    if any('高尺天空巨蛋' in x for x in result if x.startswith('LOCATION:')):
        result.insert(-1, 'GEO:37.49817;126.86707')
        result.insert(-1, 'X-APPLE-STRUCTURED-LOCATION;VALUE=URI;X-ADDRESS="서울특별시 구로구 경인로 430";X-APPLE-RADIUS=100;X-TITLE="高尺天空巨蛋":geo:37.49817,126.86707')
    category = duration_category(title)
    if category and starts and not any(x.startswith(('DTEND', 'DURATION')) for x in result):
        start = datetime.strptime(starts[0][8:], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        result.insert(-1, 'DTEND:' + fmt(start + timedelta(minutes=DEFAULT_MINUTES[category])))
        for i, line in enumerate(result):
            if line.startswith('DESCRIPTION:'):
                result[i] += '\\n结束时间为估计，实际以官方安排为准。'
                break
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
            default_estimated = False
            category = duration_category(e['title'], e.get('duration_category'))
            if end is None and category is not None:
                end = start + timedelta(minutes=DEFAULT_MINUTES[category])
                default_estimated = True
            startline, endline = 'DTSTART:' + fmt(start), ('DTEND:' + fmt(end) if end else None)
        else:
            raise ValueError('all_day must be boolean')
        if end is not None and end <= start:
            raise ValueError('end must follow start')
        if e.get('end_estimated') and (e['all_day'] or end is None):
            raise ValueError('estimated end requires a timed event with end')
        desc = e.get('details', e.get('description', ''))
        if e.get('end_estimated') or (not e['all_day'] and default_estimated):
            desc += '\n结束时间为估计，实际以官方安排为准。'
        if e.get('time_tbd'):
            if not e['all_day']:
                raise ValueError('time_tbd requires date-only event')
            note = '具体时间未记录（日期占位）' if e.get('historical') else '具体时间待公布（日期占位）'
            desc = note + '\n' + desc
        if not e.get('historical'):
            desc += '\n官方公告: ' + e['source_url']
        if e.get('watch_url') and not e.get('historical'):
            url = urlparse(e['watch_url'])
            if url.scheme != 'https' or not url.netloc:
                raise ValueError('watch_url must be HTTPS')
        lines += ['BEGIN:VEVENT', 'UID:' + uid + '@tws-calendar', 'DTSTAMP:' + fmt(updated), 'LAST-MODIFIED:' + fmt(updated), 'SEQUENCE:' + str(e['sequence']), startline]
        if endline:
            lines.append(endline)
        location = e.get('location', '').split('\nhttps://maps.apple.com/', 1)[0]
        if any(s in location for s in ('具体会场未公开', '具体会场另行通知')):
            location = ''
        if location and not e.get('geo'):
            location = map_location(location)
            if e.get('map_query'):
                query = e['map_query']
                if not isinstance(query, str) or not query.strip() or len(query) > 300:
                    raise ValueError('invalid map query')
                if 'https://maps.apple.com/' not in location:
                    location += '\nhttps://maps.apple.com/?q=' + quote_plus(query)
        if e.get('watch_url') and not e.get('historical') and e['watch_url'] not in location:
            location = '\n'.join(filter(None, (location, e['watch_url'])))
        if location:
            lines.append('LOCATION:' + escape(location))
        if e.get('geo'):
            lat, lon = e['geo']
            if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not location:
                raise ValueError('invalid location coordinates')
            place = location.split('\n', 1)[0]
            label, sep, address = place.partition(' · ')
            def parameter(value):
                return value.replace('^', '^^').replace('"', "^'").replace('\n', '^n')
            lines.append('GEO:' + str(lat) + ';' + str(lon))
            params = ';X-ADDRESS="' + parameter(address) + '"' if sep and address else ''
            lines.append('X-APPLE-STRUCTURED-LOCATION;VALUE=URI' + params + ';X-APPLE-RADIUS=100;X-TITLE="' + parameter(label) + '":geo:' + str(lat) + ',' + str(lon))
        lines += ['SUMMARY:' + escape(e['title']), 'DESCRIPTION:' + escape(desc)]
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
    events += json.loads(Path('data/auto_events.json').read_text(encoding='utf-8'))
    if not isinstance(events, list):
        raise ValueError('events must be an array')
    Path('site').mkdir(exist_ok=True)
    original = Path('data/original.ics').read_text(encoding='utf-8')
    Path('site/tws.ics').write_bytes(build(events, original))

