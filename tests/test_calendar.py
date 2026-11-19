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


if __name__ == '__main__': unittest.main()

