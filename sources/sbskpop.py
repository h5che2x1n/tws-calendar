"""Monitor recent public SBSKPOP previews without guessing ambiguous events."""
import json
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

CHANNEL = 'https://www.youtube.com/@SBSKPOP'
CHANNEL_ID = 'UCS_hnpJLQTvBkqALgapi_4g'
WEEKDAYS = '월화수목금토일'
MEMBERS = {
    '申惟': ('신유', 'SHINYU'), '道勋': ('도훈', 'DOHOON'),
    '荣宰': ('영재', 'YOUNGJAE'), '韩振': ('한진', 'HANJIN'),
    '志勋': ('지훈', 'JIHOON'), '炅玟': ('경민', 'KYUNGMIN'),
}


def initial_data(html):
    marker = 'ytInitialData = '
    position = html.find(marker)
    if position < 0:
        raise ValueError('YouTube page data unavailable')
    return json.JSONDecoder().raw_decode(html[position + len(marker):])[0]


def recent_videos(html):
    data = initial_data(html)
    try:
        tabs = data['contents']['twoColumnBrowseResultsRenderer']['tabs']
        grids = [t['tabRenderer']['content']['richGridRenderer']['contents']
                 for t in tabs if 'richGridRenderer' in t.get('tabRenderer', {}).get('content', {})]
    except (KeyError, TypeError) as exc:
        raise ValueError('YouTube channel layout changed') from exc
    found = []
    for items in grids:
        for item in items:
            content = item.get('richItemRenderer', {}).get('content', {})
            lock = content.get('lockupViewModel', {})
            if lock:
                video_id = lock.get('contentId', '')
                title = lock.get('metadata', {}).get('lockupMetadataViewModel', {}).get('title', {}).get('content', '')
            else:
                old = content.get('videoRenderer', {})
                video_id = old.get('videoId', '')
                title = ''.join(run.get('text', '') for run in old.get('title', {}).get('runs', []))
            if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id) and title:
                found.append((video_id, title))
    if not found:
        raise ValueError('YouTube channel has no recognizable videos')
    return found


def video_info(html, expected_id=None):
    data = initial_data(html)
    try:
        current_id = data['currentVideoEndpoint']['watchEndpoint']['videoId']
        sections = data['contents']['twoColumnWatchNextResults']['results']['results']['contents']
        primary = next(x['videoPrimaryInfoRenderer'] for x in sections if 'videoPrimaryInfoRenderer' in x)
        secondary = next(x['videoSecondaryInfoRenderer'] for x in sections if 'videoSecondaryInfoRenderer' in x)
        title = ''.join(run.get('text', '') for run in primary['title'].get('runs', []))
        if not title:
            title = primary['title'].get('simpleText', '')
        owner = secondary['owner']['videoOwnerRenderer']['navigationEndpoint']['browseEndpoint']['browseId']
        description = secondary['attributedDescription']['content']
    except (KeyError, TypeError, StopIteration) as exc:
        raise ValueError('YouTube preview details unavailable') from exc
    if owner != CHANNEL_ID or (expected_id and current_id != expected_id) or not title or not description:
        raise ValueError('YouTube video is not verified as an SBSKPOP preview')
    return title, description


def release(title, description, today):
    """Extract only this show's unambiguous Korean release announcement."""
    upper = title.upper()
    if not (('TWS' in upper or '투어스' in title) and ('예고' in title or 'TEASER' in upper)):
        raise ValueError('YouTube preview requires manual review')
    if not all(word in title for word in ('순간뽀짝', '세상에', '아이돌')):
        raise ValueError('YouTube preview requires manual review')
    names = [name for name, aliases in MEMBERS.items() if any(alias in upper for alias in aliases)]
    if not names:
        raise ValueError('YouTube preview members are unclear')
    if re.search(r'취소|연기|변경|휴방', description):
        raise ValueError('YouTube preview may mention a schedule change')
    pattern = r'(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*(?:\(([월화수목금토일])\)\s*)?(오전|오후|저녁|밤|새벽)\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?\s*(?:공개|방송|업로드)'
    matches = list(re.finditer(pattern, description))
    if len(matches) != 1:
        raise ValueError('YouTube preview release time is ambiguous')
    year, month, day, weekday, period, hour, minute = matches[0].groups()
    hour, minute = int(hour), int(minute or 0)
    if not 1 <= hour <= 12 or minute > 59:
        raise ValueError('YouTube preview release time is invalid')
    if period in ('오후', '저녁', '밤'):
        hour = hour % 12 + 12
    else:
        hour %= 12
    possibilities = []
    for y in ([int(year)] if year else [today.year, today.year + 1]):
        try:
            day_value = date(y, int(month), int(day))
        except ValueError:
            continue
        if today <= day_value <= today + timedelta(days=60) and (not weekday or WEEKDAYS[day_value.weekday()] == weekday):
            possibilities.append(day_value)
    if len(possibilities) != 1:
        raise ValueError('YouTube preview date is not a unique upcoming date')
    start = datetime.combine(possibilities[0], datetime.min.time(), tzinfo=timezone(timedelta(hours=9)))
    return start.replace(hour=hour, minute=minute), names


def video_id(url):
    parsed = urlparse(url)
    if parsed.netloc in ('www.youtube.com', 'youtube.com') and parsed.path == '/watch':
        value = parse_qs(parsed.query).get('v', [''])[0]
    elif parsed.netloc == 'youtu.be':
        value = parsed.path.lstrip('/')
    else:
        return ''
    return value if re.fullmatch(r'[A-Za-z0-9_-]{11}', value) else ''


def scan(fetch, events, original, today, now, *, auto=None):
    """Add a uniquely identified SBS preview or retain it for review."""
    videos = recent_videos(fetch(CHANNEL + '/videos'))
    candidates = {vid: title for vid, title in videos
                  if ('TWS' in title.upper() or '투어스' in title) and ('예고' in title or 'TEASER' in title.upper())}
    all_events = events + (auto or [])
    for event in all_events:
        vid = video_id(event.get('source_url', ''))
        if vid and event.get('location') == CHANNEL and event['start'][:10] >= today.isoformat():
            candidates.setdefault(vid, event['title'])
    result = {'added': [], 'updated': [], 'pending_review': []}
    original_text = re.sub(r'\r?\n[ \t]', '', original)
    for vid in candidates:
        url = 'https://www.youtube.com/watch?v=' + vid
        existing = [e for e in all_events if video_id(e.get('source_url', '')) == vid]
        try:
            title, description = video_info(fetch(url), vid)
            start, names = release(title, description, today)
        except Exception as exc:
            result['pending_review'].append({'url': url, 'reason': str(exc)})
            continue
        if len(existing) > 1 or (not existing and vid in original_text):
            result['pending_review'].append({'url': url, 'reason': 'possible duplicate YouTube event'})
            continue
        if existing:
            event = existing[0]
            if event.get('status') != 'confirmed':
                continue
            old_start = None if event['all_day'] else datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
            if old_start and old_start.astimezone(timezone.utc) == start.astimezone(timezone.utc):
                continue
            if event.get('end') and not event['all_day'] and not event.get('end_estimated'):
                result['pending_review'].append({'url': url, 'reason': 'confirmed end requires review after time change'})
                continue
            duration = timedelta(hours=1)
            if old_start and event.get('end'):
                duration = datetime.fromisoformat(event['end'].replace('Z', '+00:00')) - old_start
            event.update(start=start.isoformat(), end=(start + duration).isoformat(), all_day=False,
                         end_estimated=True, sequence=event['sequence'] + 1, updated_at=now)
            event.pop('time_tbd', None)
            event['title'] = event['title'].replace('（时间待定）', '')
            result['updated'].append({'id': event['id'], 'url': url})
            continue
        start_utc = start.astimezone(timezone.utc)
        same_start = any(not e['all_day'] and datetime.fromisoformat(e['start'].replace('Z', '+00:00')).astimezone(timezone.utc) == start_utc for e in all_events)
        duplicate_id = any(e['id'] == 'youtube-sbs-' + vid for e in all_events)
        if same_start or duplicate_id or start_utc.strftime('%Y%m%dT%H%M%SZ') in original_text:
            result['pending_review'].append({'url': url, 'reason': 'possible duplicate at same time'})
            continue
        label = '、'.join(names)
        event = {'id': 'youtube-sbs-' + vid, 'title': '📺 ' + label + '｜《순간뽀짝 세상에 이런 아이돌이》',
                 'status': 'confirmed', 'sequence': 0, 'all_day': False,
                 'start': start.isoformat(), 'end': (start + timedelta(hours=1)).isoformat(),
                 'end_estimated': True, 'duration_category': 'variety', 'updated_at': now,
                 'location': CHANNEL, 'details': label + '出演 SBSKPOP X INKIGAYO 线上综艺。',
                 'source_url': url, 'remind_at_start': True}
        events.append(event)
        all_events.append(event)
        result['added'].append({'id': event['id'], 'url': url})
    return result
