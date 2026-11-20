"""Summarize automated coverage without treating unparsed material as checked."""
import json
import os
from pathlib import Path

file = Path('source-report.json')
if file.exists():
    report = json.loads(file.read_text(encoding='utf-8'))
    lines = ['## 官方来源自动检查', '']
    if report.get('error'):
        lines += ['**检查失败；没有保存更新。**', '', report['error'], '']
    else:
        lines += [f"新增：{len(report['added'])}；更新：{len(report['updated'])}；待人工核查：{len(report['pending_review'])}。", '',
                  '日本官网：检查未来日程；仅识别格式明确的电视与电台播出。', '',
                  'Weverse：只重查已知、格式受支持的人气歌谣和音乐中心 MC 公告，无法自动发现新公告。', '',
                  'PLEDIS 与 X：需要人工核查。', '']
        if report['pending_review']:
            lines += ['### 待人工核查', '']
            explanations = {
                'existing imported event; changes require review': '已有导入事件，变更需人工核对',
                'existing curated event; changes require review': '已有人工整理事件，变更需人工核对',
                'source has multiple event records': '同一来源对应多条活动，需确认对应关系',
                'schedule category requires manual extraction': '此类活动尚需人工提取',
                'possible duplicate at same time': '同一时间已有活动，需核对是否重复',
                'event missing from current index; cancellation not assumed': '当前目录未显示该活动，不能据此认定取消',
                'ambiguous Weverse event identity': '公告与已有活动的对应关系不明确',
                'confirmed end requires review after time change': '开始时间变化，已确认的结束时间需重新核对',
            }
            for item in report['pending_review']:
                url = item['url'].replace(')', '%29').replace('\n', '')
                reason = explanations.get(item['reason'], item['reason']).replace('|', '\\|').replace('\n', ' ')
                lines.append(f"- {url} — {reason}")
            lines.append('')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as out:
            out.write('\n'.join(lines))
    else:
        print('\n'.join(lines))

