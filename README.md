# TWS 官方行程订阅

这是一个尚需维护的日历发布系统。已核实行程保存在 `data/events.json`；当前为空。每天北京时间 09:23 及手动运行时重新验证、生成并部署。**当前没有自动采集或自动新增行程**：PLEDIS、Weverse 和日本官网需要人工核查、录入；不能把成功部署当成来源采集成功。现有 ChatGPT 搜索任务不会自动写入此仓库。

## 首次启用

仓库 Settings → Pages → Build and deployment → Source 选择 GitHub Actions。进入 Actions → Build and deploy calendar → Run workflow。检查任务成功后打开 `https://h5che2x1n.github.io/tws-calendar/tws.ics`，确认返回 VCALENDAR 文本而非 404。iPhone 日历 → 日历 → 添加日历 → 添加订阅日历，输入此网址。Apple 刷新有延迟，不能保证立即更新。取消的表现取决于订阅客户端；保留取消记录以利同步。

## 添加和修改

编辑 `data/events.json`，仅收录官方确认的信息。格式示例使用虚构数据，不是实际行程：

```json
[{"id":"example-stable-id","title":"虚构示例","status":"confirmed","sequence":0,"all_day":false,"start":"2030-01-01T20:00:00+09:00","end":"2030-01-01T21:00:00+09:00","updated_at":"2029-12-01T00:00:00Z","source_url":"https://example.org/notice","watch_url":"https://example.org/watch","description":"说明"}]
```

实际活动必须核实开始与结束时间及偏移量；时间不明确不得推测或标为全天。真正的全天活动使用 `all_day: true`，开始、结束用 `YYYY-MM-DD`，结束是排他的次日日期。`watch_url` 和 `description` 可省略。每个活动分配唯一永久 id，改期沿用 id 并递增 sequence、更新 updated_at；取消时保留记录，将 status 设为 cancelled、递增 sequence、更新 updated_at。不要删除已发布事件或复用 id。提交后工作流发布。禁止将上面的示例写入实际数据。

来源：日本官网 https://tws-official.jp/schedule 、PLEDIS https://www.pledis.co.kr/ko/artist/detail/TWS/notice/ 。公告可能有图片、未明确结束时间或需要登录；人工核对并记录来源。未知结束时间的活动当前不能发布。

## 维护检查

GitHub 的定时工作流在公开仓库长期无活动时可能自动停用。每月至少检查一次 Actions 最近运行时间和结果，手动 Run workflow 验证；收到 GitHub 定时停用提醒时重新启用。启用 GitHub 的 Actions 失败通知并检查邮件设置；工作流不运行时不会产生失败邮件，需独立检查或外部监控。访问固定 ICS URL 检查部署是否新鲜。工作流测试使用虚构、内存内的事件，不写入生产日历。

