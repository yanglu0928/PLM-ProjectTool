# OUT-01-A01-P35：生成文件用户检索链编码前检查

- 日期：2026-11-06
- 结论：PASS_WITH_LIMITATION（检查完成，发现单一产品缺口）
- 基线：冻结 API Contract V1 的 OUTPUT_REQUEST_GET/LIST、OUT-02 OutputArtifact、Document/DocumentVersion/Storage 合同；CR-OUT-028、CR-OUT-031；P34B Storage发布验收。
- 执行边界：只读 GitHub 源码；未在用户本机或 C 盘运行代码；未用客户数据、未生成文件。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core。
- 当前 WBS：OUT-01-A01-P35。
- 输入基线：OUTPUT_REQUEST_GET/LIST、OUT-02、Document/DocumentVersion frozen contracts、P34A/P34B。
- 前置任务：P34A 与 P34B 均 PASS_SCOPE_LIMITED；P25 独立 BLOCKED_DIAGNOSTIC，不作为本项前置。
- 涉及模块：Output read projection、Document authorized read/download、Project authorization、输出历史前端。
- 涉及实体：OutputRequest、OutputArtifact、Document、DocumentVersion、FileObject；无新增实体。
- 涉及 API：当前 OutputRequest GET/LIST 不变；拟加一个独立 Artifact 引用 GET endpoint；下载继续走 Document content 路由。
- 涉及权限：沿用会话、可信来源/CSRF、License 和当前项目读取授权；只按 ProjectId + OutputRequestId 定位，Artifact 必须 AVAILABLE 且关联固定 DocumentVersion；跨项目/缺失/不可用统一失败关闭。
- 验收标准：PG18 合成数据验证单个 AVAILABLE 引用；请求未成功、Artifact 非 AVAILABLE、错误项目、缺失/冲突引用均不泄露路径且不返回可下载引用；权限、许可、下载 Hash/大小复核及审计保持有效；前端只在 SUCCEEDED 且 API 返回精确有效引用时显示下载。
- 风险：公开新字段会改变既有冻结 GET 响应及其精确字段解析；直接给前端裸 Document/Version ID 会缺少输出请求归属证明；内部路径外泄会绕过 Storage 校验。
- 决定：不修改现有 GET/LIST projection；新增独立、opt-in OutputArtifact 引用读取路由，在同一 OutputRequest/Project 查询中绑定 Artifact 与 DocumentVersion；返回身份、hash、size、MIME 及受控下载 route，不返回 Storage locator。由既有 Document下载 service 二次进行Project授权及完整Hash/大小快照校验。
- 回滚：移除新增 route/service/repository/UI入口即可；不改 Schema/既有 API/Output生成事实，已发布 DocumentVersion与历史保留。
- 验收执行：GitHub hosted Windows Server 2025 D: runner 与临时 PostgreSQL 18、纯合成数据；定向 unit/API/权限/PG18 断言，后端全量、wheel、前端 test/build，并运行可独立通过的父包与A17/A34/A35/A50检查。P25 0xC0000135独立失败不得阻止此 WBS，也不得虚报整体workflow通过。

## 源码核查结论

1. P34B通过范围是受控Storage提升、FileObject AVAILABLE、P34A DocumentVersion/source ref/SYSTEM Audit与P33 Artifact/Job成功事务；没有产品Worker或HTTP用户检索验证。
2. OutputRequest详情的固定投影仅含请求、版本源、状态、Job与Execution等字段，不含OutputArtifact、Document或DocumentVersion身份。既有 GET /api/v1/projects/{project_id}/output-requests/{output_request_id} 保持冻结，只读状态投影。
3. 输出历史前端仅展示输出状态，并明确提示文件是否已可下载需另行判断；当前没有Output Artifact client、内容下载链接或按钮。
4. Document已有项目授权列表/版本读取和内容下载服务。内容下载在读取前后重新确认固定版本来源，并用Storage按预期SHA-256/大小打开完整快照；但这是独立Document访问链，OutputRequest无法直接解析到它。
5. Document/Output路由由可选router composition提供；opt-in HTTP代码存在不能当作Windows服务已挂载的证据。

## 结论

缺口是一个边界明确的用户纵向链：OutputRequest没有安全地暴露其AVAILABLE OutputArtifact所绑定的DocumentVersion引用，前端因此无法从成功请求进入校验下载。通过新的独立只读API与输出历史入口可在不改变冻结既有响应、不改Schema、不暴露物理路径的条件下补齐。实施边界见CR-OUT-032。