# SOL-04-A16：Section 前端只读/创建链前置核查

日期：2026-10-09。结果：`SOL_04_A16_SECTION_FRONTEND_PRECHECK_PASS`；仅静态对账和施工拆分，Section 前端尚不可用。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A16。
- 输入基线：Gate 2 冻结 API-04 `SOL_SECTION_CREATE/GET/LIST`、CR-SOL-012、A04/A08/A14 HTTP 与 A15 Windows 显式组合；前置已满足。
- 模块/实体/API/权限：Solution 前端与 SessionClient；Section 身份/项目内 Outline 父项，冻结 `/api/v1` 不变。当前项目成员可读；仅 PM/实施成员可写，最终服务端复验。
- 验收：确认传输、严格投影、分页/路由、创建幂等和浏览器证据缺口并拆成单一 WBS；本项不声称新代码、真实浏览器或正式账户验收。
- 风险：Section 身份/批准指针被误展示为已交付正文；列表 cursor 与 Outline 家族串用；创建结果不明时换 Key；导航把未授权用户暴露为可写。

## 静态发现与顺序

后端路径为项目内 `solution-sections`：LIST 固定最小摘要及专用签名 cursor；GET 另含 `created_by` 和强 ETag；CREATE 仅接收同项目 `solution_outline_id` 与 `section_key`，返回初态 `ACTIVE`/`v0`，不创建正文、版本或评审。现有前端仅有 Outline 的列表/详情/创建客户端和页面；`SessionClient` 没有 Section 创建命令；Router 只有 Outline 路由，Outline 详情也没有 Section 导航。不可复用 Outline cursor 或把批准版引用解读为已核实正文。

1. `SOL-04-A17`：独立 Section 安全只读客户端及合同测试。严格字段、Project/Section 绑定、详情 Header ETag、分页序、cursor 和失败关闭；保持与 Outline 客户端隔离。
2. `SOL-04-A18`：Section 列表/详情页面与 Outline 详情入口、Router 和页面合同。只读按当前项目成员展示；空/错误/换项目/翻页处理；界面声明仅为身份，不代表已批准方案内容。
3. `SOL-04-A19`：`SessionClient` 受保护 Section CREATE 命令、创建客户端和合同测试。验证父 OutlineId/ProjectId、`section_key` 规范、当前角色及 exact 201/Location/ETag/Trace；结果不明保留同一 Idempotency-Key。
4. `SOL-04-A20`：Section 创建页/入口/路由及合同。只从已读取的父 Outline 导航，当前角色门控；浏览器会话保存原操作号，失败不自动换号重试。
5. `SOL-04-A21`：Windows 11 隔离 PostgreSQL 18.6/真实 Session 的浏览器读/写链和负例独立验收；正式目标账户、20 并发、Server2025 和发行另验。

兼容/升级/回滚：本项只新增进度文档，无程序、Schema/Migration、依赖或冻结 API 变化；施工顺序可按证据调整，既有 Section 历史不可因 UI 回滚删除。验证：静态核对合同、客户端、Router、页面和生产组合，未运行新测试。TraceLink：Gate 2/API-04 → CR-SOL-012/A15 → A16 → A17～A21。
