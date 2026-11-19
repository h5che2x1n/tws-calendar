"""Map queries for known venues. Do not add regions or undisclosed locations."""
from urllib.parse import quote_plus

VENUES = {
    '首尔 高尺天空巨蛋': 'Gocheok Sky Dome Seoul',
    '韩国首尔 · 蚕室室内体育馆': 'Jamsil Indoor Stadium Seoul',
    '韩国首尔 · 奥林匹克手球竞技场': 'Olympic Handball Gymnasium Seoul',
    '韩国首尔 · ticketLINK LIVE ARENA': 'Olympic Handball Gymnasium Seoul',
    'KSPO DOME': 'KSPO Dome Seoul',
    '韩国仁川 · INSPIRE Arena': 'INSPIRE Arena Incheon',
    '日本东京 · 武藏野之森综合体育广场': 'Musashino Forest Sport Plaza Tokyo',
    '日本神奈川 · ぴあアリーナMM': 'Pia Arena MM Yokohama',
    '日本 · 广岛文化学园 HBG Hall': 'Hiroshima Bunka Gakuen HBG Hall',
    '日本 · Niterra 日本特殊陶业市民会馆 Forest Hall': 'Niterra Forest Hall Nagoya',
    '日本 · 福冈 Sunpalace': 'Fukuoka Sunpalace',
    '日本 · 仙台 Sunplaza Hall': 'Sendai Sunplaza Hall',
    '日本 · Orix Theater': 'Orix Theater Osaka',
    '日本 · K-Arena Yokohama': 'K Arena Yokohama',
    'K-Arena Yokohama': 'K Arena Yokohama',
    '福冈国际中心': 'Fukuoka Kokusai Center',
    '神户 World Hall': 'Kobe World Hall',
    '伦敦人综艺馆': 'Londoner Arena Macau',
    '中国澳门 · 影汇综艺馆': 'Studio City Event Center Macau',
    '中国台湾高雄 · 高雄流行音乐中心': 'Kaohsiung Music Center',
    '中国台湾高雄 · 国家体育场': 'Kaohsiung National Stadium',
    '高雄巨蛋': 'Kaohsiung Arena Taiwan',
    'Arena @ EXPO': 'Arena Singapore Expo',
    'IDEA LIVE, BRAVO BKK': 'IDEA LIVE BRAVO BKK Bangkok',
    '泰国曼谷 · IMPACT Challenger Hall': 'Impact Challenger Bangkok',
    '中国香港 · 启德主场馆': 'Kai Tak Stadium Hong Kong',
    '美国洛杉矶 · Dolby Theatre': 'Dolby Theatre Los Angeles',
    '日本东京 · 国立竞技场': 'Japan National Stadium Tokyo',
    '日本福冈 · 福冈巨蛋': 'Fukuoka PayPay Dome',
    '韩国一山 · MBC Dream Center': 'MBC Dream Center Goyang',
    '首尔 Megabox COEX MX4D': 'Megabox COEX Seoul',
    '首尔 上岩 MBC': 'MBC Sangam Seoul',
    '韩国首尔 · MBC': 'MBC Sangam Seoul',
    '首尔 龙山区 汉江大路42号 1F': '42 Hangang daero Yongsan Seoul',
}


def map_location(value):
    query = VENUES.get(value)
    if not query:
        return value
    return value + '\nhttps://maps.apple.com/?q=' + quote_plus(query)

