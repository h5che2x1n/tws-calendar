"""Display-only formatting; source evidence and duration metadata stay intact."""
import re


MEMBER_ALIASES = {
    'SHINYU': '申惟', '신유': '申惟', '申惟': '申惟',
    'DOHOON': '道勋', '도훈': '道勋', '道勋': '道勋',
    'YOUNGJAE': '英宰', '영재': '英宰', '英宰': '英宰',
    'HANJIN': '韩振', '한진': '韩振', '韩振': '韩振',
    'JIHOON': '志薰', '지훈': '志薰', '志薰': '志薰', '志勋': '志薰',
    'KYUNGMIN': '炅潣', '경민': '炅潣', '炅潣': '炅潣',
}
BOILERPLATE = re.compile(
    r'结束时间为(?:估计|估算|预计)[，,；;]?\s*(?:实际以官方安排为准[。.]?)?'
    r'|实际以官方安排为准[。.]?')


def member_prefix(title):
    if '生日' in title:
        return ''
    head = re.split(r'[｜|]', title, maxsplit=1)[0]
    if re.search(r'\bTWS\b', head, re.I):
        return ''
    head = re.sub(r'^[^\w\u3400-\u9fff]+', '', head).strip()
    tokens = re.split(r'[、,/／]+', head)
    names = [MEMBER_ALIASES.get(x.strip().upper(), x.strip()) for x in tokens]
    known = set(names) & set(MEMBER_ALIASES.values())
    if not known or len(known) == 6:
        return ''
    # Keep explicitly named collaborators alongside TWS members.
    return '、'.join(names)


def format_notes(title, details):
    if not member_prefix(title) and not BOILERPLATE.search(details):
        return details
    cleaned = BOILERPLATE.sub('', details)
    cleaned = '\n'.join(line for line in cleaned.split('\n') if line.strip()).strip()
    prefix = member_prefix(title)
    if not prefix:
        return cleaned
    lines = cleaned.split('\n') if cleaned else []
    fallback = re.split(r'[｜|]', title, maxsplit=1)[-1].strip()
    if not lines or re.match(r'(?:官方(?:来源|公告|预告)\s*[:： ]|来源[:：]|https?://|节目开始时间：|官方公告列明)', lines[0]):
        lines.insert(0, fallback)
    elif lines[0] == '官方图文原帖。':
        lines[0] = fallback
    if lines[0].startswith(prefix + '｜'):
        return '\n'.join(lines)
    # Remove a repeated leading subject only where the remaining clause is grammatical.
    aliases = [prefix] + [key for key, value in MEMBER_ALIASES.items() if value == prefix]
    for name in sorted(aliases, key=len, reverse=True):
        if re.match(re.escape(name) + r'\s*(?:出演|担任|出席|参加)', lines[0], re.I):
            lines[0] = re.sub('^' + re.escape(name) + r'\s*', '', lines[0], flags=re.I)
            break
    lines[0] = prefix + '｜' + lines[0]
    return '\n'.join(lines)
