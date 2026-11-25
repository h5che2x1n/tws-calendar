import unittest
from calendar_build import build, duration_category
from note_format import format_notes


class CalendarPreferencesTests(unittest.TestCase):
    def event(self, **kwargs):
        event = dict(id='preference-test', title='TWS Vlog', status='confirmed',
                     sequence=1, all_day=False, start='2030-01-01T20:00:00+09:00',
                     source_url='https://example.org/official', updated_at='2029-12-01T00:00:00Z')
        event.update(kwargs)
        return event

    def calendar(self, event):
        return build([event]).decode('utf-8').replace('\r\n ', '')

    def test_video_defaults_to_thirty_minutes(self):
        for title in ('TWS Vlog', '幕后花絮', 'Music Bank Behind', 'TWS 비하인드'):
            with self.subTest(title=title):
                text = self.calendar(self.event(title=title))
                self.assertIn('DTEND:20300101T113000Z', text)
                self.assertNotIn('结束时间为估计', text)

    def test_known_video_end_takes_priority(self):
        text = self.calendar(self.event(end='2030-01-01T20:07:33+09:00'))
        self.assertIn('DTEND:20300101T110733Z', text)
        self.assertNotIn('结束时间为估计', text)

    def test_reviewed_date_only_video_has_no_invented_time(self):
        text = self.calendar(self.event(all_day=True, start='2024-01-01',
            end='2024-01-02', historical=True, time_tbd=True, hide_time_tbd_note=True))
        self.assertIn('DTSTART;VALUE=DATE:20240101', text)
        self.assertIn('DTEND;VALUE=DATE:20240102', text)
        self.assertNotIn('日期占位', text)
        self.assertNotIn('结束时间为估计', text)

    def test_future_and_unreviewed_notes_remain(self):
        base = self.event(all_day=True, start='2030-01-01', end='2030-01-02', time_tbd=True)
        self.assertIn('具体时间待公布（日期占位）', self.calendar(dict(base, hide_time_tbd_note=True)))
        self.assertIn('具体时间未记录（日期占位）', self.calendar(dict(base, historical=True)))

    def test_photo_behind_is_not_video(self):
        self.assertIsNone(duration_category('📷 TWS｜概念照 Behind'))
        self.assertIsNone(duration_category('TWS Concept Photo Behind'))

    def test_hidden_note_does_not_bypass_time_validation(self):
        with self.assertRaises(ValueError):
            build([self.event(time_tbd=True, historical=True, hide_time_tbd_note=True)])

    def test_partial_members_prefix_notes_without_duplicate_prefix(self):
        text = format_notes('🎬 炅潣｜2027 Season’s Greetings · Safety Video',
                            '年历企划官方宣传短片（预告）。')
        self.assertEqual(text, '炅潣｜年历企划官方宣传短片（预告）。')
        self.assertEqual(format_notes('🎬 炅潣｜Safety Video', text), text)
        self.assertEqual(format_notes('📺 SHINYU、DOHOON｜Show', ''), '申惟、道勋｜Show')
        self.assertEqual(format_notes('📺 TWS｜Show', '全员出演。'), '全员出演。')
        self.assertEqual(format_notes('📺 申惟、道勋、英宰、韩振、志薰、炅潣｜Show',
                                     '全员出演。'), '全员出演。')

    def test_remove_only_estimated_end_boilerplate(self):
        text = self.calendar(self.event(end_estimated=True, end='2030-01-01T20:30:00+09:00',
            details='结束时间为估计，实际以官方安排为准。\n集合信息通知中签者。'))
        self.assertNotIn('结束时间为估计', text)
        self.assertIn('集合信息通知中签者。', text)
        self.assertIn('DTEND:20300101T113000Z', text)


if __name__ == '__main__':
    unittest.main()

