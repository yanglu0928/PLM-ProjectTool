# SUR-02-A06-P02：Round 前端与 Windows 11 真实浏览器

日期：2026-10-06。结论：`SUR_02_A06_P02_ROUND_FRONTEND_BROWSER_PASS`。`SUR-02-A06` 至此整体完成；下一项进入 `SUR-03-A08` Assignment/Response HTTP 与 Windows 组合。

## 实现

- 新增严格 Round 前端客户端：LIST/GET 强父级、cursor、ETag、字段集合、状态生命周期与来源快照；CREATE/PATCH/OPEN/CLOSE/CANCEL 由既有 SessionClient 持有 CSRF，写入绑定 If-Match/Idempotency-Key，未知结果不自动换 Key 或重试。
- 新增项目 Round 工作台及项目/Survey 导航。ProjectManager 可 CREATE/PATCH/OPEN/CLOSE/CANCEL，ImplementationMember 仅 CREATE/PATCH；页面明确 PLANNED/OPEN 不是客户确认事实，CLOSE 仍由服务端重验全部 Assignment/Response/Evidence。
- 写后清除旧事实并重新 LIST/GET；只有重读结果才显示为当前状态。CLOSE 不完整显示安全业务提示；网络不确定时仅在本页内存保留原操作号、版本和正文。
- Windows 11 验收使用一次性 Edge profile、隔离 PostgreSQL 18.6、合成已批准 Survey Version、生产 FastAPI 和构建后 Vue 同源组合；完成两次 CREATE、PATCH、OPEN、CLOSE 422 失败关闭、CANCEL、列表/详情共40条浏览器网络证据及三张截图，随后清理数据库、凭据、profile和临时文件。

## 偏差、兼容与回滚

- 首轮真实浏览器暴露新增 SessionClient 方法直接以对象接收者调用原生 `window.fetch`，Edge 在网络发送前拒绝；改为先分离 fetch 函数再调用，并新增接收者回归测试。该问题未产生服务端写入。
- 第二轮首次成功 CREATE 后，严格解析错误假设 `updated_by` 必为 UUID；实际冻结投影允许新建 Round 为 `null`。客户端改为接受 `UUID|null`，未修改服务端合同或数据库。
- 原 Survey 来源定位 fixture 只创建 DRAFT Version，不能用于 Round。P02 wrapper 仅在隔离验收库中把合成 Version 提升为 APPROVED/current approved，不更改产品种子、生产数据或运行逻辑。
- 无 Schema/Migration、公开 URL/JSON、角色、依赖、Secret 或数据外发变化。应用回滚可删除页面、客户端、导航和 SessionClient Round transport；已提交 Round/Audit/receipt 历史必须保留。主 JS `658.73 kB` 的既有分块提示继续登记，不影响本轮本机功能验收。

## 验证与已知问题

- 前端定向14项、全量84文件1455项、TypeScript typecheck、Vite 176模块生产构建通过；真实 Edge 标记 `SUR_02_A06_P02_EDGE_BROWSER_PASS`，隔离环境清理通过。
- 截图位于本机忽略目录 `artifacts/sur-02-a06-p02-round-browser/`，不作为程序源代码推送；可复现脚本随仓库提交。
- Assignment/Response HTTP、Windows组合和前端仍待 `SUR-03-A08/A09`；Conclusion、完整模拟项目、Gate 3/UAT、Windows Server 2025发行复验和可使用程序包仍待。Debian 13实机按用户指令跳过，但仍为正式兼容目标。
