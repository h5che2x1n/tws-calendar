"""Refresh supported official sources and keep ambiguous items for human review."""
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from sources.japan import BASE, Detail, Listing, extract
from sources.weverse import extract_mc

AGENT = 'TWSCalendarBot/1.0'
MAX_BYTES = 2_000_000


def canonical(url):
    u = urlparse(url)
    return u.scheme + '://' + u.netloc.lower() + u.path.rstrip('/')


class Fetcher:
    def __init__(self):
        self.rules = {}

    def request(self, url):
        last = None
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers={'User-Agent': AGENT}), timeout=25) as response:
                    if urlparse(response.geturl()).netloc != urlparse(url).netloc:
                        raise ValueError('unexpected redirect host')
                    content = response.read(MAX_BYTES + 1)
                    if len(content) > MAX_BYTES:
                        raise ValueError('official page too large')
                    return content.decode('utf-8')
            except HTTPError as exc:
                if exc.code in (403, 404, 410):
                    raise
                last = exc
            except (OSError, UnicodeError) as exc:
                last = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
        raise last

    def __call__(self, url):
        u = urlparse(url)
        if u.scheme != 'https' or u.netloc not in ('tws-official.jp', 'weverse.io'):
            raise ValueError('unapproved source host')
        if u.netloc not in self.rules:
            robots = RobotFileParser()
            try:
                rules = self.request(f'https://{u.netloc}/robots.txt').splitlines()
            except HTTPError as exc:
                if exc.code != 404:
                    raise
                rules = []
            robots.parse(rules)
            self.rules[u.netloc] = robots
        if not self.rules[u.netloc].can_fetch(AGENT, url):
            raise ValueError('robots.txt disallows this source')
        return self.request(url)


def future_japan(fetch, today):
    rows = []
    previous = None
    for page in range(1, 21):
        html = fetch(BASE + '/schedule' + (f'?page={page}' if page > 1 else ''))
        parser = Listing()
        parser.feed(html)
        if not parser.rows:
            raise ValueError('Japan schedule page has no recognizable entries')
        for row in parser.rows:
            if previous and row['date'] > previous:
                raise ValueError('Japan schedule is no longer sorted by date')
            previous = row['date']
            if row['date'] >= today:
                rows.append(row)
        if parser.rows[-1]['date'] < today:
            return rows
    raise ValueError('Japan schedule exceeded 20 pages; manual review required')


def original_index(original):
    text = re.sub(r'\r?\n[ \t]', '', original)
    blocks = re.findall(r'BEGIN:VEVENT\s*([\s\S]*?)\s*END:VEVENT', text)
    urls, starts = set(), set()
    for block in blocks:
        for url in re.findall(r'https://[^\s\\;]+', block):
            urls.add(canonical(url))
        m = re.search(r'^DTSTART:(\d{8}T\d{6}Z)', block, re.M)
        if m:
            starts.add(m.group(1))
    return urls, starts


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def ics_stamp(value):
    return instant(value).strftime('%Y%m%dT%H%M%SZ')


def refresh(events, auto, original, fetch, today, now):
    report = {'checked_at': now, 'added': [], 'updated': [], 'pending_review': [],
              'coverage': {'japan_schedule': 'scanned',
                           'weverse': 'known MC notice URLs only; new-notice discovery unavailable',
                           'pledis': 'manual; notice list unavailable',
                           'x': 'manual; no permitted stable feed configured'}}
    originals, original_starts = original_index(original)
    auto_by_id = {e['id']: e for e in auto}
    if len(auto_by_id) != len(auto):
        raise ValueError('duplicate automatic event id')
    ids = {e['id'] for e in events}
    if ids & set(auto_by_id):
        raise ValueError('automatic event id collides with curated event')
    all_events = events + auto
    source_counts = Counter(canonical(e['source_url']) for e in all_events)
    rows = future_japan(fetch, today)
    seen_urls = Counter(canonical(r['url']) for r in rows)
    for row in rows:
        key = canonical(row['url'])
        if key in originals:
            report['pending_review'].append({'url': key, 'reason': 'existing imported event; changes require review'})
            continue
        if seen_urls[key] > 1 or source_counts[key] > 1:
            report['pending_review'].append({'url': key, 'reason': 'source has multiple event records'})
            continue
        if row['kind'] not in ('TV', 'RADIO'):
            report['pending_review'].append({'url': key, 'reason': 'schedule category requires manual extraction'})
            continue
        detail = Detail()
        detail.feed(fetch(row['url']))
        text = detail.text()
        if not text:
            raise ValueError('Japan schedule detail unavailable: ' + key)
        try:
            event, reason = extract(row, text)
        except (ValueError, OverflowError):
            event, reason = None, 'invalid broadcast date or time'
        if event is None:
            report['pending_review'].append({'url': key, 'reason': reason})
            continue
        uid = event['id']
        if key in {canonical(x['source_url']) for x in events}:
            report['pending_review'].append({'url': key, 'reason': 'existing curated event; changes require review'})
            continue
        existing = auto_by_id.get(uid)
        if not existing:
            start = ics_stamp(event['start'])
            curated_starts = {ics_stamp(e['start']) for e in events + auto if not e['all_day']}
            if start in original_starts or start in curated_starts:
                report['pending_review'].append({'url': key, 'reason': 'possible duplicate at same time'})
                continue
            event.update(sequence=0, updated_at=now)
            auto.append(event)
            auto_by_id[uid] = event
            report['added'].append({'id': uid, 'url': key})
        else:
            # Keep identifiers and bump sequence only for real material changes.
            comparable = {k: v for k, v in existing.items() if k not in ('sequence', 'updated_at')}
            if comparable != event:
                if existing.get('end') and not event.get('end'):
                    report['pending_review'].append({'url': key, 'reason': 'previously published end time disappeared'})
                    continue
                event.update(sequence=existing['sequence'] + 1, updated_at=now)
                existing.clear()
                existing.update(event)
                report['updated'].append({'id': uid, 'url': key})

    for event in auto:
        if date.fromisoformat(event['start'][:10]) >= today and canonical(event['source_url']) not in seen_urls:
            report['pending_review'].append({'url': canonical(event['source_url']), 'reason': 'event missing from current index; cancellation not assumed'})

    # Independently recheck only notices with a unique, already-curated identity.
    for event in events:
        u = urlparse(event.get('source_url', ''))
        if u.netloc != 'weverse.io' or '人气歌谣' not in event['title'] or not any(n in event['title'] for n in ('申惟', 'SHINYU')):
            continue
        if date.fromisoformat(event['start'][:10]) < today:
            continue
        key = canonical(event['source_url'])
        if source_counts[key] != 1 or key in originals:
            report['pending_review'].append({'url': key, 'reason': 'ambiguous Weverse event identity'})
            continue
        try:
            new_start = extract_mc(event, fetch(event['source_url']))
        except ValueError as exc:
            report['pending_review'].append({'url': key, 'reason': str(exc)})
            continue
        if new_start is None:
            continue
        if event['all_day'] or instant(event['start']) != new_start.astimezone(timezone.utc):
            if event.get('end') and not event['all_day'] and not event.get('end_estimated'):
                report['pending_review'].append({'url': key, 'reason': 'confirmed end requires review after time change'})
                continue
            if event.get('end') and not event['all_day']:
                old_duration = instant(event['end']) - instant(event['start'])
                event['end'] = (new_start + old_duration).isoformat()
            else:
                event.pop('end', None)
                event.pop('end_estimated', None)
            event['start'] = new_start.isoformat()
            event['all_day'] = False
            event.pop('time_tbd', None)
            event['title'] = event['title'].replace('（时间待定）', '')
            event['sequence'] += 1
            event['updated_at'] = now
            report['updated'].append({'id': event['id'], 'url': key})
    return report


def main():
    event_path = Path('data/events.json')
    auto_path = Path('data/auto_events.json')
    report_path = Path('source-report.json')
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    today = (now + timedelta(hours=8)).date()
    updated = now.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    try:
        events = json.loads(event_path.read_text(encoding='utf-8'))
        auto = json.loads(auto_path.read_text(encoding='utf-8'))
        original = Path('data/original.ics').read_text(encoding='utf-8')
        report = refresh(events, auto, original, Fetcher(), today, updated)
        # Validate the full calendar before persisting any updates.
        from calendar_build import build
        history = json.loads(Path('data/history.json').read_text(encoding='utf-8'))
        build(events + history + auto, original)
        for path, value in ((event_path, events), (auto_path, auto)):
            new = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
            if path.read_text(encoding='utf-8') != new:
                path.write_text(new, encoding='utf-8')
    except Exception as exc:
        report = {'checked_at': updated, 'error': str(exc), 'status': 'failed; no updates saved'}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
        return 1
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

