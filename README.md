# TWS 官方行程订阅

`data/original.ics` 保存原始快照；`data/events.json` 维护人工整理及部分自动更新的行程；`data/history.json` 收录历史行程；`data/auto_events.json` 保存程序从日本官方日程识别的活动。历史来源保存在数据中，不显示在历史日历详情。原 UID 和生日重复规则继续保留。

GitHub Actions 每天北京时间 09:00 执行自动检查，并在 09:23 再检查一次，尽量弥补定时任务延迟或漏跑；手动触发或向 main 提交也会运行。程序会检查日本官网当前和未来日程，自动识别其中格式明确、只有一个日期的电视或电台节目；对已有数据中符合特定格式的人气歌谣申惟 MC Weverse 公告，重查官方开始时间。通过验证的更新写回仓库后由同一次工作流部署到原订阅网址，电脑不需要开机。工作流不能保证准时执行，Apple 日历也有刷新延迟。

**覆盖范围并不完整。**目前程序不能自动发现 Weverse 新公告，不能自动解析 PLEDIS、X 的新公告，不能可靠解析图片、复杂多场行程、签售、取消或成员不明确的节目。日本官网复杂活动、与既有记录可能重复的条目等列入人工核查，不会因为未找到而当作取消；已导入的原始事件和人工整理的日本官网事件也不会自动改期。`source-review` 工件及 Actions 运行摘要列出待核查项目和来源限制，成功仅表示受支持部分的程序运行成功，不表示检查完所有官方来源。需要定期人工检查 Weverse、X、PLEDIS 和主办方通知，并将核实的新增或变更写入 `data/events.json`。

## 首次启用

仓库 Settings → Pages → Build and deployment → Source 选择 GitHub Actions。进入 Actions → Build and deploy calendar → Run workflow。检查任务成功后打开 `https://h5che2x1n.github.io/tws-calendar/tws.ics`，确认返回 VCALENDAR 文本而非 404。iPhone 日历 → 日历 → 添加日历 → 添加订阅日历，输入此网址。Apple 刷新有延迟，不能保证立即更新。取消的表现取决于订阅客户端；保留取消记录以利同步。

## 添加和修改

编辑 `data/events.json`，仅收录官方确认的信息。格式示例使用虚构数据，不是实际行程：

```json
[{"id":"example-stable-id","title":"虚构示例","status":"confirmed","sequence":0,"all_day":false,"start":"2030-01-01T20:00:00+09:00","end":"2030-01-01T21:00:00+09:00","updated_at":"2029-12-01T00:00:00Z","source_url":"https://example.org/notice","watch_url":"https://example.org/watch","description":"说明"}]
```

实际活动必须核实开始时间及偏移量；不可推测开始时刻。仅日期已确认但时刻待定时可用 `all_day: true`、`time_tbd: true` 表示日期占位；时刻公布后沿用同一个 id 改成定时事件，递增 sequence。结束时间确定则填写；有合理时长依据时可以估计，设置 `end_estimated: true`，日历会标明结束时间为估计；没有依据时省略 `end`。线上综艺有确定播出时间时设置 `remind_at_start: true`；实际提醒受 Apple 日历订阅和设备通知设置影响。全天日期使用 `YYYY-MM-DD`，结束是排他的次日日期。`location` 放线下场馆及已确认可直接观看或参与的链接，没有则留空；不把公告网址当成观看入口。`details` 简述活动和成员，非全员活动须注明确切成员；`source_url` 是官方通知，`watch_url` 是已核实的观看链接。不要写核验过程或内部维护说明。节目、打歌、MC、电台、综艺、演出和官方签售等均可收录，须有官方确认。每个活动分配唯一永久 id，改期沿用 id 并递增 sequence、更新 updated_at；取消时保留记录，不复用 id。提交后工作流发布。

来源：日本官网 https://tws-official.jp/schedule 、PLEDIS https://www.pledis.co.kr/ko/artist/detail/TWS/notice/ 。公告可能有图片或需要登录；人工核对并记录来源。

## 维护检查

GitHub 的定时工作流在公开仓库长期无活动时可能自动停用。每月至少检查一次 Actions 最近运行时间和结果，手动 Run workflow 验证；收到 GitHub 定时停用提醒时重新启用。启用 GitHub 的 Actions 失败通知并检查邮件设置；工作流不运行时不会产生失败邮件，需独立检查或外部监控。访问固定 ICS URL 检查部署是否新鲜。工作流使用仓库 `GITHUB_TOKEN` 的 contents 写权限提交验证通过的日历数据；如果分支保护禁止 Actions 直接提交、仓库限制写权限或推送时发生冲突，工作流会失败并保留上一版本，需检查 Actions 日志。测试使用虚构、内存内的事件，不写入生产日历。
# 默认时长

仅当已知具体开始时间而未提供结束时间时，生成器根据活动类型填入估计时长并在详情标注。已知官方结束时间或正片长度优先。允许设置 `duration_category`：`video_fansign` 60 分钟、`offline_fansign` 120 分钟、`year_end` 240 分钟、`music_bank` 90 分钟、`music_core` 80 分钟、`inkigayo` 70 分钟、`radio` 120 分钟、`variety` 60 分钟。未标注时仅对可识别标题推断；无法分类和预录活动不推断。日期待定或只有日期的活动不补时间。线上签售为整场估计，不是每人的通话时间；电台按整档节目，已知成员片段时间时应使用片段实际时间。修改已发布活动时必须沿用 UID 并提高 sequence。


