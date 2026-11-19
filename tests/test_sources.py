import unittest
from sources.scan import Links


class LinksTest(unittest.TestCase):
    def test_collects_anchor_text_without_creating_events(self):
        parser = Links()
        parser.feed('<a href="/schedule/abc">TWS <b>公演</b></a><a href="/x">other</a>')
        self.assertEqual(parser.links, [('/schedule/abc', 'TWS 公演'), ('/x', 'other')])

