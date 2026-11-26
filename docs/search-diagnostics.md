# Apple Calendar search diagnostic — 2026-11-26

This opt-in fixture tests search behavior for a small, standards-based calendar
independently of the production event set.

## Verified server checks

The public `tws.ics` returned HTTP 200 with `Content-Type: text/calendar` and
519100 bytes. SHA-256:
`357b380fe77583b3bb41cb2ba4f25d3e06a8ef46c26c6d6b719dd11f554957e9`.

It contains 1184 events with unique UIDs. Every event has UID, DTSTAMP, DTSTART,
and SUMMARY. UTF-8 decoding succeeds; lines use CRLF, are folded at no more than
75 octets, and have no BOM. An independent `icalendar` parser reports no errors;
decoded end dates/times, when present, follow the start. The downloaded bytes
match the locally generated production calendar. This is not proof that Apple's
search implementation will index it correctly, and does not establish a cause.

## Separate diagnostic feed

`site/search-check.ics` is a static, opt-in diagnostic published by the existing
Pages workflow, which uploads the whole `site` directory. It does not alter
`tws.ics`, production event data, event UIDs, or the fixed subscription URL.

There are exactly two synthetic test events, with no alarms, no links, no
recurrence, and no busy-time blocking. Both are explicitly tests, not TWS events:

| Test | Beijing time | Title |
| --- | --- | --- |
| A | 2026-11-27 12:00–12:05 | CALCHECK A Search Test |
| B | 2026-11-27 12:10–12:15 | 📺 CALCHECK B｜TWS 搜索测试 |

Add `https://h5che2x1n.github.io/tws-calendar/search-check.ics` as a separate
subscription. After confirming both events are visible on November 27, search
for `CALCHECK`. Do not remove or re-import the production subscription.

- Both found: the device can search a small subscription from this host; inspect
  the production feed's content, size, and feed-specific indexing next. This
  does not prove a numerical event limit or rule out a feed-specific cache.
- Only one found: record which one; the title/description encoding difference is
  a candidate, not a confirmed cause.
- Neither found but both visible: this minimal feed also reproduces the search
  failure. Account/device indexing or host-related processing remains possible;
  don't attribute the issue to the production event count or complex fields yet.
- Events not visible: this is a loading test failure; it says nothing about search.

After testing, unsubscribe only from the diagnostic feed. Remove this static
file once diagnosis is complete. A successful deployment is not a successful
iPhone search test; the subscribing client must be tested separately.
