# SOL-03-A04-P03-P03-P06-A01：OutlineVersion CREATE 前端安全请求桥

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P06_A01_OUTLINE_VERSION_CLIENT_PASS`；仅客户端合同，不宣称页面/真实浏览器可用。

## 编码前检查

|字段|核查|
|---|---|
|当前 Phase / WBS|Phase 2 Platform Core / 本任务|
|输入基线|Gate 2 冻结 API-04、CR-SOL-016/017、已验 P05-A01～A03 HTTP/Win11 写装配|
|前置任务|OutlineVersion Owner、固定来源证明、HTTP 路由、Windows 显式写组合已验证|
|涉及模块/实体|前端 SessionClient 与 Solution OutlineVersion DRAFT 请求/首响投影|
|涉及 API|既有 `POST /api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions`；不改后端合同|
|涉及权限|本项目 ProjectManager / ImplementationMember；服务端仍二次强制鉴权|
|验收标准|固定 Section/Requirement/Reference/声明输入，CSRF 和原 Idempotency-Key，严格 201 回执/Location/Trace，权限/非法输入/未知提交结果失败关闭；前端全量测试、类型与构建|
|风险|网络超时可能发生已提交但无回执；客户端只报告“不确定”，不自行生成新操作号|

## 实施与证据

SessionClient 增加唯一受控版本创建路径与 512 KiB UTF-8 请求上限；通用桥仍采用 same-origin Cookie、CSRF、无缓存/无重定向，不向调用者暴露 CSRF。新增 Solution 创建客户端，预检本项目角色、固定引用集合/唯一性/声明大小和原操作号；严格校验 201 DRAFT 首响的项目/目录/版本、计数、指纹、Review 空态、Location 和 Trace。可确认的服务端拒绝单独映射，不可判定的网络/响应失败保留原操作号语义。页面将另行实现来源候选与持久同号恢复，不在本任务提供裸 UUID 输入或对外开放按钮。

验证：定向 Vitest 4/4；前端全量 122 文件、1710/1710；`pnpm typecheck` 与 `pnpm build` 均退出 0。构建保留现有主 chunk >500 KiB 告警。无数据库 Migration、后端 API、权限策略、依赖变化；撤回客户端及桥接方法即可回滚未接 UI 功能，已有服务端历史不可删除。

已知限制：来源候选选择页、原号恢复 UI、Win11 浏览器/PG 端到端、正式服务账户信任源、Server2025、20 并发、Gate3/UAT/发行仍未完成；Debian13 实机依用户指令跳过。下一独立项为 P06-A02 页面候选与安全确认。

TraceLink：Gate2 API-04 → CR-SOL-016/017 → P05-A01/A02/A03 → 本请求桥 → P06-A02 页面 → P06-A03 浏览器。
