import copy
import unittest
from datetime import date

from sources.japan import Listing, Detail, extract
from sources.update import refresh


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

    def test_multi_date_and_members_go_to_review(self):
        parser = Listing(); parser.feed(LIST)
        row = parser.rows[0]
        e, reason = extract(row, '放送日時：1月5日(土)～1月7日(月) 20:00')
        self.assertIsNone(e)
        e, reason = extract(row, 'DOHOON 出演\n放送日時：1月5日(土) 20:00')
        self.assertIsNone(e)
        self.assertIn('member', reason)

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

