"""Synthetic fixtures only: no test events are published."""
import json
import unittest
from datetime import date

from sources.sbskpop import CHANNEL, CHANNEL_ID, release, scan

ID = 'fakeID00001'
URL = 'https://www.youtube.com/watch?v=' + ID
TITLE = '[예고] TWS 한진 가상편 | #순간뽀짝세상에이런아이돌이'
NOW = '2030-01-01T00:00:00Z'
TODAY = date(2030, 1, 1)


def channel():
    lock = {'contentId': ID, 'metadata': {'lockupMetadataViewModel': {'title': {'content': TITLE}}}}
    tab = {'tabRenderer': {'content': {'richGridRenderer': {'contents': [
        {'richItemRenderer': {'content': {'lockupViewModel': lock}}}]}}}}
    return 'ytInitialData = ' + json.dumps({'contents': {'twoColumnBrowseResultsRenderer': {'tabs': [tab]}}})


def watch(description='가상 프로그램 1월 5일 저녁 6시 공개', owner=CHANNEL_ID):
    primary = {'videoPrimaryInfoRenderer': {'title': {'runs': [{'text': TITLE}]}}}
    secondary = {'videoSecondaryInfoRenderer': {
        'owner': {'videoOwnerRenderer': {'navigationEndpoint': {'browseEndpoint': {'browseId': owner}}}},
        'attributedDescription': {'content': description}}}
    data = {'currentVideoEndpoint': {'watchEndpoint': {'videoId': ID}},
            'contents': {'twoColumnWatchNextResults': {'results': {'results': {'contents': [primary, secondary]}}}}}
    return 'ytInitialData = ' + json.dumps(data, ensure_ascii=False)


def fetch_for(body):
    def fetch(url):
        if url == CHANNEL + '/videos': return channel()
        if url == URL: return watch(body)
        raise AssertionError(url)
    return fetch


class SbsKpopTest(unittest.TestCase):
    def test_unique_preview_is_added_with_reminder_and_not_duplicated(self):
        events = []
        result = scan(fetch_for('가상 프로그램 1월 5일 저녁 6시 공개'), events, '', TODAY, NOW)
        self.assertEqual(len(result['added']), 1)
        event = events[0]
        self.assertEqual(event['start'], '2030-01-05T18:00:00+09:00')
        self.assertEqual(event['end'], '2030-01-05T19:00:00+09:00')
        self.assertTrue(event['end_estimated'])
        self.assertTrue(event['remind_at_start'])
        self.assertIn('韩振', event['title'])
        self.assertEqual(event['location'], CHANNEL)
        self.assertEqual(event['source_url'], URL)
        again = scan(fetch_for('가상 프로그램 1월 5일 저녁 6시 공개'), events, '', TODAY, NOW)
        self.assertEqual(again['added'], [])
        self.assertEqual(again['updated'], [])
        self.assertEqual(len(events), 1)

    def test_existing_id_is_preserved_when_date_changes(self):
        events = []
        scan(fetch_for('가상 프로그램 1월 5일 저녁 6시 공개'), events, '', TODAY, NOW)
        events[0]['id'] = 'previously-curated-id'
        changed = scan(fetch_for('가상 프로그램 1월 6일 저녁 7시 공개'), events, '', TODAY, NOW)
        self.assertEqual(len(changed['updated']), 1)
        self.assertEqual(events[0]['id'], 'previously-curated-id')
        self.assertEqual(events[0]['sequence'], 1)
        self.assertEqual(events[0]['start'], '2030-01-06T19:00:00+09:00')
        self.assertEqual(events[0]['end'], '2030-01-06T20:00:00+09:00')

    def test_multiple_release_times_or_cancellation_are_not_guessed(self):
        for body in ('1월 5일 저녁 6시 공개 1월 6일 저녁 7시 공개', '1월 5일 저녁 6시 공개 취소'):
            events = []
            result = scan(fetch_for(body), events, '', TODAY, NOW)
            self.assertFalse(events)
            self.assertTrue(result['pending_review'])

    def test_unverified_channel_and_duplicate_are_not_added(self):
        def fetch(url):
            return channel() if url.endswith('/videos') else watch(owner='UCNotTheVerifiedChannel')
        events = []
        result = scan(fetch, events, '', TODAY, NOW)
        self.assertFalse(events)
        self.assertTrue(result['pending_review'])
        result = scan(fetch_for('1월 5일 저녁 6시 공개'), events,
                      'BEGIN:VEVENT\nDESCRIPTION:' + URL + '\nEND:VEVENT', TODAY, NOW)
        self.assertFalse(events)
        self.assertTrue(result['pending_review'])

    def test_missing_members_and_weekday_mismatch_are_not_guessed(self):
        with self.assertRaises(ValueError):
            release('[예고] TWS 가상편 순간뽀짝세상에이런아이돌이', '1월 5일 저녁 6시 공개', TODAY)
        with self.assertRaises(ValueError):
            release(TITLE, '1월 5일 (월) 저녁 6시 공개', TODAY)

    def test_existing_automatic_event_at_same_time_requires_review(self):
        auto = [{'id': 'other-auto', 'all_day': False, 'start': '2030-01-05T18:00:00+09:00',
                 'source_url': 'https://example.org/other'}]
        events = []
        result = scan(fetch_for('1월 5일 저녁 6시 공개'), events, '', TODAY, NOW, auto=auto)
        self.assertFalse(events)
        self.assertTrue(result['pending_review'])


if __name__ == '__main__':
    unittest.main()
