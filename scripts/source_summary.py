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
                  'Weverse：只重查已知、格式受支持的人气歌谣 MC 公告，无法自动发现新公告。', '',
                  'PLEDIS 与 X：需要人工核查。', '']
        if report['pending_review']:
            lines += ['### 待人工核查', '']
            for item in report['pending_review']:
                url = item['url'].replace(')', '%29').replace('\n', '')
                reason = item['reason'].replace('|', '\\|').replace('\n', ' ')
                lines.append(f"- {url} — {reason}")
            lines.append('')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as out:
            out.write('\n'.join(lines))
    else:
        print('\n'.join(lines))

