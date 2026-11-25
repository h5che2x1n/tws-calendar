import unittest
from copy import deepcopy
from calendar_build import build


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.event = dict(id='fictional-test', title='虚构测试,活动;例', status='confirmed', sequence=0, all_day=False, start='2030-01-01T20:00:00+09:00', end='2030-01-01T21:00:00+09:00', source_url='https://example.org/fictional', updated_at='2029-12-01T00:00:00Z')

    def test_change_and_cancel(self):
        first = build([self.event])
        changed = deepcopy(self.event)
        changed.update(start='2030-01-02T20:00:00+09:00', end='2030-01-02T21:00:00+09:00', sequence=1, status='cancelled')
        second = build([changed])
        self.assertIn(b'UID:fictional-test@tws-calendar', first)
        self.assertIn(b'UID:fictional-test@tws-calendar', second)
        self.assertIn(b'DTSTART:20300102T110000Z', second)
        self.assertIn(b'STATUS:CANCELLED', second)
        self.assertIn(b'SEQUENCE:1', second)

    def test_all_day_and_fold(self):
        self.event.update(all_day=True, start='2030-01-01', end='2030-01-02', title='测试' * 50)
        output = build([self.event])
        self.assertIn(b'DTEND;VALUE=DATE:20300102', output)
        self.assertTrue(all(len(line) <= 75 for line in output.split(b'\r\n')))
        output.decode('utf-8')

    def test_reject_unverified_time_and_duplicates(self):
        self.event['start'] = '2030-01-01T20:00:00'
        with self.assertRaises(ValueError): build([self.event])
        with self.assertRaises(ValueError): build([dict(self.event, start='2030-01-01T20:00:00+09:00')] * 2)

    def test_unknown_end_is_not_invented(self):
        del self.event['end']
        self.assertNotIn(b'DTEND', build([self.event]))

    def test_estimated_end_metadata_does_not_add_boilerplate(self):
        self.event.update(end_estimated=True)
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('DTEND:20300101T120000Z', data)
        self.assertNotIn('结束时间为估计', data)
        del self.event['end']
        with self.assertRaises(ValueError): build([self.event])

    def test_location_and_details(self):
        self.event.update(location='首尔, 韩国', details='成员：TWS\n具体会场待公布')
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('LOCATION:首尔\\, 韩国', data)
        self.assertIn('成员：TWS\\n具体会场待公布', data)

    def test_structured_map_location(self):
        self.event.update(location='虚构场馆 · 虚构地址 1 号', geo=[35.0, 139.0])
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('X-ADDRESS="虚构地址 1 号"', data)
        self.assertIn('X-TITLE="虚构场馆":geo:35.0,139.0', data)
        self.assertIn('GEO:35.0;139.0', data)

    def test_watch_url_is_in_location_and_source_in_details(self):
        self.event.update(location='体育场', watch_url='https://example.org/live')
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('LOCATION:体育场\\nhttps://example.org/live', data)
        self.assertIn('官方公告: https://example.org/fictional', data)
        self.assertNotIn('观看链接:', data)

    def test_date_placeholder_is_explicit(self):
        self.event.update(all_day=True, time_tbd=True, start='2030-01-01', end='2030-01-02')
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('具体时间待公布（日期占位）', data)

    def test_original_uid_and_recurrence_preserved_and_override(self):
        original = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:fictional-test@tws-calendar\nRRULE:FREQ=YEARLY\nSUMMARY:旧记录\nEND:VEVENT\nEND:VCALENDAR\n'
        untouched = build([], original).decode('utf-8')
        self.assertIn('RRULE:FREQ=YEARLY', untouched)
        updated = build([self.event], original).decode('utf-8')
        self.assertEqual(updated.count('UID:fictional-test@tws-calendar'), 1)
        self.assertNotIn('旧记录', updated)

    def test_original_does_not_show_maintenance_notes(self):
        original = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:old@tws-calendar\nSEQUENCE:0\nDTSTAMP:20260101T000000Z\nDESCRIPTION:演出介绍。\\n核对日期：2026-11-07。导入后不会自动更新。\\n来源：https://example.org\nEND:VEVENT\nEND:VCALENDAR\n'
        data = build([], original).decode('utf-8').replace('\r\n ', '')
        self.assertIn('演出介绍。\\n来源：https://example.org', data)
        self.assertNotIn('核对日期', data)
        self.assertNotIn('不会自动更新', data)
        self.assertIn('SEQUENCE:6', data)

    def test_venue_map_and_unknown_location(self):
        self.event.update(location='韩国首尔 · 蚕室室内体育馆')
        data = build([self.event]).decode('utf8').replace('\r\n ', '')
        self.assertIn('https://maps.apple.com/?q=Jamsil+Indoor+Stadium+Seoul', data)
        self.event['location'] = '具体会场未公开'
        self.assertNotIn('LOCATION:', build([self.event]).decode('utf8'))

    def test_default_duration_and_explicit_end(self):
        self.event.update(title='虚构线上视频签售')
        del self.event['end']
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('DTEND:20300101T120000Z', data)
        self.assertNotIn('结束时间为估计', data)
        self.event['end'] = '2030-01-01T22:00:00+09:00'
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('DTEND:20300101T130000Z', data)
        self.assertNotIn('结束时间为估计', data)

    def test_variety_default_and_no_prerecording_guess(self):
        self.event.update(title='TWS TOURS in BANGKOK EP.1')
        del self.event['end']
        self.assertIn(b'DTEND:20300101T120000Z', build([self.event]))
        self.event['title'] = '虚构音乐中心预录'
        self.assertNotIn(b'DTEND', build([self.event]))

    def test_historical_source_stays_in_data_not_calendar(self):
        self.event['historical'] = True
        data = build([self.event]).decode('utf-8')
        self.assertNotIn('https://example.org/fictional', data)

    def test_online_variety_reminder_at_start(self):
        self.event.update(remind_at_start=True)
        data = build([self.event]).decode('utf-8')
        self.assertIn('BEGIN:VALARM\r\nTRIGGER:PT0S\r\nACTION:DISPLAY', data)
        self.event.update(status='cancelled')
        self.assertNotIn('BEGIN:VALARM', build([self.event]).decode('utf-8'))
        self.event.update(status='confirmed', all_day=True, start='2030-01-01', end='2030-01-02')
        with self.assertRaises(ValueError): build([self.event])

    def test_more_than_twelve_hours_is_all_day_with_original_time_in_details(self):
        self.event.update(start='2030-01-01T08:00:00+09:00', end='2030-01-01T20:00:00+09:00')
        exact = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('DTSTART:20291231T230000Z', exact)
        self.assertIn('DTEND:20300101T110000Z', exact)
        self.event['end'] = '2030-01-01T20:01:00+09:00'
        long = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('UID:fictional-test@tws-calendar', long)
        self.assertIn('DTSTART;VALUE=DATE:20300101', long)
        self.assertIn('DTEND;VALUE=DATE:20300102', long)
        self.assertIn('活动时间：2030-01-01 08:00—2030-01-01 20:01（韩国／日本时间）', long)
        self.assertIn('官方公告: https://example.org/fictional', long)

    def test_long_event_crossing_midnight_and_midnight_end(self):
        self.event.update(start='2030-01-01T12:00:00+09:00', end='2030-01-02T01:00:00+09:00')
        two_days = build([self.event]).decode('utf-8')
        self.assertIn('DTSTART;VALUE=DATE:20300101', two_days)
        self.assertIn('DTEND;VALUE=DATE:20300103', two_days)
        self.event.update(start='2030-01-01T10:00:00+09:00', end='2030-01-02T00:00:00+09:00')
        ending_midnight = build([self.event]).decode('utf-8')
        self.assertIn('DTEND;VALUE=DATE:20300102', ending_midnight)

    def test_long_event_uses_start_timezone_and_reminds_at_actual_start(self):
        self.event.update(start='2030-01-01T10:00:00+09:00', end='2030-01-01T23:30:00+08:00', remind_at_start=True)
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('DTSTART;VALUE=DATE:20300101', data)
        self.assertIn('DTEND;VALUE=DATE:20300103', data)
        self.assertIn('TRIGGER;VALUE=DATE-TIME:20300101T010000Z', data)
        self.assertNotIn('TRIGGER:PT0S', data)

    def test_long_imported_event_keeps_uid_and_updates_sequence(self):
        original = ('BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:old-long@tws-calendar\nSEQUENCE:2\n'
                    'DTSTAMP:20290101T000000Z\nDTSTART:20291231T160000Z\nDTEND:20300101T050000Z\n'
                    'SUMMARY:虚构长活动\nDESCRIPTION:活动介绍。\nEND:VEVENT\nEND:VCALENDAR\n')
        data = build([], original).decode('utf-8').replace('\r\n ', '')
        self.assertIn('UID:old-long@tws-calendar', data)
        self.assertIn('SEQUENCE:9', data)
        self.assertIn('DTSTART;VALUE=DATE:20300101', data)
        self.assertIn('DTEND;VALUE=DATE:20300102', data)
        self.assertIn('2030-01-01 00:00—2030-01-01 13:00（北京时间）', data)


if __name__ == '__main__': unittest.main()


