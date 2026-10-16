# SOL-03-A04-P03-P03-P06-A02-P01：OutlineVersion PROJECT 候选与创建页

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P06_A02_P01_PROJECT_PAGE_PASS`；仅 PROJECT 候选前端合同，真实浏览器/PG 和 GLOBAL 页面未验。

## 编码前检查

|字段|核查|
|---|---|
|当前 Phase/WBS|Phase 2 Platform Core / 本项目 PROJECT 候选页|
|输入基线|Gate2 冻结 API-04、CR-SOL-016/017/018、DEC-1141/1144、P06-A01 安全请求桥|
|前置任务|Section/Requirement/PROJECT Reference 现有受权只读客户端及 CREATE Owner/HTTP/Windows 写链已验|
|模块/实体/API|前端 Solution 页面和只读候选聚合；当前 Outline、Section、Requirement、PROJECT Reference；只调用既有 GET 与冻结 CREATE POST|
|权限|本项目 ProjectManager/ImplementationMember；读取/写入由服务端各自重验，GLOBAL 管理员列表不复用|
|验收|全部分页、跨项目/重复/状态过滤失败关闭；人工逐项选固定版本、可点详情、声明填写提示、原号/原内容恢复、角色拒绝；全量前端测试/typecheck/build|
|风险|候选读取与提交之间状态可变，服务端必须最终重证；GLOBAL 候选需 CR-SOL-018 安全只读面，不可借管理员权限|

## 实施与验证

候选聚合只使用本项目既有只读客户端，遍历全部分页，过滤本目录 ACTIVE Section、ACTIVE 且有已批准版指针的 Requirement、当前列表标记 ELIGIBLE 的 PROJECT Reference；跨项目、重复身份、分页异常、失败读取及超过 CREATE 容量均阻止提交。列表不构成资格证明。页面提供来源详情导航、明确缺失/冲突声明示例、DRAFT 非批准提示；选定固定版本后，原 Draft/操作号先保存在当前浏览器会话，不确定响应后的重试必须重新明确勾选且复用原内容/原号。创建成功只显示固定版本 ID，不伪造尚无的版本详情页。GLOBAL 暂不展示可提交候选，拒绝裸 UUID。

候选定向 3 项、页面定向 3 项；前端全量 124 文件/1716 项通过，typecheck/build 退出 0，保留既有主 chunk >500 KiB 告警。测试曾发现损坏待恢复记录的错误提示被并发加载清空，已修复并全量重跑。无 DB/Migration、冻结 API/角色/依赖变化；可撤项目候选路由/页面而不删已创建版本历史。

限制：PROJECT 页面尚未在 Win11 真实浏览器/PG 验收；GLOBAL 项目安全候选读面仍缺，见 CR-SOL-018；正式服务账户/Server2025、质量/性能/Review/UAT/Gate3/发行仍待。下一项先完成 CR-SOL-018 的读面设计及实现，再做双 Scope 浏览器验收。Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04 → CR-SOL-016/017/018 → DEC-1144 → P06-A01 安全请求桥 → 本 PROJECT 页面 → GLOBAL 候选读面 → 双 Scope 浏览器。
