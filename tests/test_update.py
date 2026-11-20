import copy
import unittest
from datetime import date

from sources.japan import Listing, Detail, extract
from sources.update import refresh, scan_japan_news, track_known_sources, original_official_sources
from sources.weverse import extract_mc, extract_video_fansign


LIST = '''<div class="news__container"><div><p class="news__text">2030.01.05</p>
<p class="news__text">|</p><p class="news__text">TV</p></div>
<a class="news__title" href="/schedule/example123?x=1">虚构节目</a></div>
<div class="news__container"><p class="news__text">2029.12.31</p>
<p class="news__text">|</p><p class="news__text">TV</p>
<a class="news__title" href="/schedule/old">旧节目</a></div>'''
DETAIL = '<div id="news-desc"><div>放送日時：2030年1月5日(土) 24:10～25:00</div></div>'
WEVERSE = '''<meta name="description" content="[SBS 인기가요 - MC 신유]
방송 일시 : 2030년 1월 6일(일) 14:00 PM (KST)
[인원체크 시간] 2030년 1월 6일 12:10 PM">'''
OLD = dict(id='mc-stable', title='申惟｜SBS《人气歌谣》MC', status='confirmed',
           sequence=4, all_day=False, start='2030-01-06T14:10:00+09:00',
           end='2030-01-06T15:20:00+09:00', end_estimated=True,
           updated_at='2029-12-01T00:00:00Z', source_url='https://weverse.io/tws/notice/123',
           location='https://www.sbs.co.kr/live')
ORIGINAL = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:original@tws-calendar\nDTSTART:20290101T000000Z\nSUMMARY:old\nEND:VEVENT\nEND:VCALENDAR\n'
NOW='2030-01-01T01:00:00Z'


def fetch(url):
    if '/schedule/example123' in url: return DETAIL
    if '/tws/notice/123' in url: return WEVERSE
    if url.endswith('/schedule'): return LIST
    raise AssertionError(url)


class RefreshTest(unittest.TestCase):
    def test_news_pending_is_persistent_and_respects_scan_watermark(self):
        news = '''<div class="news__container"><p class="news__text">2030.01.05</p><p class="news__text">|</p><p class="news__text">EVENT</p><a class="news__title" href="/news/abc">TWS ライブ開催</a></div>
<div class="news__container"><p class="news__text">2029.11.01</p><p class="news__text">|</p><p class="news__text">MEDIA</p><a class="news__title" href="/news/old">旧ニュース</a></div>'''
        state = {'version': 1, 'known_sources': {}, 'pending': {}}
        scan_japan_news(lambda url: news, date(2030, 1, 6), state, set())
        self.assertIn('https://tws-official.jp/news/abc', state['pending'])
        self.assertEqual(state['news_last_success'], '2030-01-06')
        scan_japan_news(lambda url: news, date(2030, 1, 7), state, set())
        self.assertIn('https://tws-official.jp/news/abc', state['pending'])
        import hashlib
        url = 'https://tws-official.jp/news/abc'
        state['resolved_news'] = {url: hashlib.sha256('TWS ライブ開催'.encode()).hexdigest()}
        del state['pending'][url]
        scan_japan_news(lambda url: news, date(2030, 1, 7), state, set())
        self.assertNotIn(url, state['pending'])

    def test_known_notice_change_is_recorded_without_deleting_events(self):
        event = copy.deepcopy(OLD)
        state = {'version': 1, 'known_sources': {}, 'pending': {}}
        track_known_sources([event], lambda url: WEVERSE, date(2030, 1, 1), state)
        self.assertEqual(state['pending'], {})
        track_known_sources([event], lambda url: WEVERSE.replace('14:00', '14:30'), date(2030, 1, 1), state)
        self.assertIn('https://weverse.io/tws/notice/123', state['pending'])
        self.assertEqual(event['start'], OLD['start'])

    def test_original_calendar_future_notice_is_tracked(self):
        original = ORIGINAL.replace('20290101T000000Z', '20300106T050000Z').replace('SUMMARY:old', 'SUMMARY:old\nDESCRIPTION:https://weverse.io/tws/notice/123')
        self.assertEqual(original_official_sources(original, date(2030, 1, 1)), {'https://weverse.io/tws/notice/123'})
        self.assertEqual(original_official_sources(original, date(2030, 1, 7)), set())

    def test_music_core_mc_uses_broadcast_not_checkin(self):
        event = dict(OLD, title='道勋｜MBC《音乐中心》MC')
        html = '<meta name="description" content="[MBC 쇼! 음악중심 - MC 도훈] 방송 일시 : 2030년 1월 6일(토) 3:15 PM (KST) [인원체크 시간] 1:30 PM">'
        self.assertEqual(extract_mc(event, html).isoformat(), '2030-01-06T15:15:00+09:00')

    def test_video_fansign_ignores_application_deadline(self):
        event = dict(OLD, title='TWS｜虚构视频签售')
        html = '<meta name="description" content="[영상통화 팬사인회] - 일시 : 2030년 1월 6일 (일) 17:00 (KST) [응모 기간] 2029년 12월 1일 10:00">'
        self.assertEqual(extract_video_fansign(event, html).isoformat(), '2030-01-06T17:00:00+09:00')
        bad = '<meta name="description" content="[응모 기간] 2030년 1월 6일 17:00 (KST)">'
        with self.assertRaises(ValueError): extract_video_fansign(event, bad)

    def test_new_broadcast_and_mc_change_are_idempotent(self):
        events, auto = [copy.deepcopy(OLD)], []
        result = refresh(events, auto, ORIGINAL, fetch, date(2030, 1, 1), NOW)
        self.assertEqual(len(result['added']), 1)
        self.assertEqual(len(result['updated']), 1)
        self.assertEqual(auto[0]['start'], '2030-01-06T00:10:00+09:00')
        self.assertEqual(auto[0]['end'], '2030-01-06T01:00:00+09:00')
        self.assertEqual(events[0]['id'], 'mc-stable')
        self.assertEqual(events[0]['sequence'], 5)
        self.assertEqual(events[0]['start'], '2030-01-06T14:00:00+09:00')
        self.assertEqual(events[0]['end'], '2030-01-06T15:10:00+09:00')
        again = refresh(events, auto, ORIGINAL, fetch, date(2030, 1, 1), '2030-01-02T01:00:00Z')
        self.assertEqual(again['added'], [])
        self.assertEqual(again['updated'], [])
        self.assertEqual(events[0]['sequence'], 5)

    def test_existing_original_source_is_never_duplicated(self):
        original = ORIGINAL.replace('SUMMARY:old', 'SUMMARY:old\nDESCRIPTION:https://tws-official.jp/schedule/example123')
        auto = []
        result = refresh([], auto, original, fetch, date(2030, 1, 1), NOW)
        self.assertEqual(auto, [])
        self.assertEqual(result['pending_review'][0]['reason'], 'existing imported event; changes require review')

    def test_original_with_matching_official_time_needs_no_duplicate_or_review(self):
        original = ORIGINAL.replace('20290101T000000Z', '20300105T151000Z').replace('SUMMARY:old', 'SUMMARY:old\nDESCRIPTION:https://tws-official.jp/schedule/example123')
        auto = []
        result = refresh([], auto, original, fetch, date(2030, 1, 1), NOW)
        self.assertEqual(auto, [])
        self.assertFalse(result['pending_review'])

    def test_multi_date_and_members_go_to_review(self):
        parser = Listing(); parser.feed(LIST)
        row = parser.rows[0]
        e, reason = extract(row, '放送日時：1月5日(土)～1月7日(月) 20:00')
        self.assertIsNone(e)
        e, reason = extract(row, 'DOHOON 出演\n放送日時：1月5日(土) 20:00')
        self.assertIsNone(e)
        self.assertIn('member', reason)

    def test_live_starts_at_showtime_not_doors_and_has_map(self):
        parser = Listing(); parser.feed(LIST)
        row = dict(parser.rows[0], kind='EVENT & LIVE', title='TWS CONCERT')
        body = '■開催日程\n2030年1月5日(土) 18:00開場 19:00開演\n■会場\n架空ホール(東京都架空区架空1-2-3)'
        event, reason = extract(row, body)
        self.assertIsNone(reason)
        self.assertEqual(event['start'], '2030-01-05T19:00:00+09:00')
        self.assertEqual(event['end'], '2030-01-05T21:30:00+09:00')
        self.assertTrue(event['end_estimated'])
        self.assertEqual(event['map_query'], '東京都架空区架空1-2-3')
        from calendar_build import build
        event.update(sequence=0, updated_at=NOW)
        self.assertIn('https://maps.apple.com/?q=', build([event]).decode('utf8').replace('\r\n ', ''))

    def test_multiple_live_shows_and_popup_are_not_guessed(self):
        parser = Listing(); parser.feed(LIST)
        row = dict(parser.rows[0], kind='EVENT & LIVE', title='TWS TOUR')
        body = '2030年1月5日(土) 14:00開演\n2030年1月5日(土) 19:00開演'
        event, reason = extract(row, body)
        self.assertIsNone(event)
        self.assertIn('multiple', reason)
        row['title'] = 'TWS TOUR POP-UP STORE'
        self.assertIsNone(extract(row, '2030年1月5日(土) 19:00開演')[0])

    def test_existing_cancellation_is_not_inferred_from_missing_page(self):
        auto = [dict(id='jp-missing',title='fixture',status='confirmed',sequence=1,all_day=False,
                     start='2030-01-04T10:00:00+09:00',source_url='https://tws-official.jp/schedule/missing')]
        result = refresh([], auto, ORIGINAL, fetch, date(2030, 1, 1), NOW)
        self.assertEqual(auto[0]['status'], 'confirmed')
        self.assertTrue(any('missing from current index' in x['reason'] for x in result['pending_review']))

    def test_same_time_collision_requires_review(self):
        e = dict(OLD, start='2030-01-06T00:10:00+09:00', source_url='https://example.org/source', title='其他活动')
        auto = []
        result = refresh([e], auto, ORIGINAL, fetch, date(2030, 1, 1), NOW)
        self.assertFalse(auto)
        self.assertTrue(any('possible duplicate' in x['reason'] for x in result['pending_review']))


if __name__ == '__main__': unittest.main()

