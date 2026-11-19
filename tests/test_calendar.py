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

    def test_location_and_details(self):
        self.event.update(location='首尔, 韩国', details='成员：TWS\n具体会场待公布')
        data = build([self.event]).decode('utf-8').replace('\r\n ', '')
        self.assertIn('LOCATION:首尔\\, 韩国', data)
        self.assertIn('成员：TWS\\n具体会场待公布', data)

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


if __name__ == '__main__': unittest.main()

