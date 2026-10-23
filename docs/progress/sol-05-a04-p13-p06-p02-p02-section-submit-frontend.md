# SOL-05-A04-P13-P06-P02-P02：章节负责人送审前端合同

日期：2026-10-23。状态：`FRONTEND_CONTRACT_PASS`；真实浏览器/PG 全链仍待。

## 编码前检查

- 输入：冻结 `/api/v1` SectionVersion `:submit-review` 四字段合同、CR-SOL-024/025、P13-P06-P01 合成 Win11/PG18 终态与 P02-P01 评审待办/详情前端。
- 单一问题：负责人如何从当前章节固定版本选择合格客户确认人并安全送审，避免网络未知结果时换操作号或评审人重试。
- 前置：后端 Session/CSRF/License/ProjectManager/当前六维/Review Owner 已独立验收；前端已有 Section 详情与 VALIDATE 报告。
- 范围：Session 同源提交桥、Section 送审客户端、详情页独立面板。无后端 Schema/API/角色/License 变化；业务资格仍以服务端实时判断为准。

## 结果与验证

- 新送审入口仅当前项目负责人且固定 DRAFT、未绑定 Review、与当前版本指纹/六维就绪报告一致时开放；项目成员分页必须完整，前端仅列 ACTIVE CUSTOMER_MANAGER/CUSTOMER_MEMBER。最多 32 人。
- 提交前将精确项目/章节/版本/客户确认人/操作号写入会话存储；未知结果保留并要求显式按原内容重试；已确认失败清除；成功提供 Review 详情链接。201 仅标送审，不宣称批准。
- 定向客户端/面板/原章节视图 10 项通过；前端全量 157 文件、1856 测试通过；typecheck 与生产构建通过（主 bundle 超 500kB 的构建警告仍在）。
- 尚未运行 Win11 真实浏览器中的“负责人点击送审 → 客户待办/固定章节 → 决定”链。该缺口移至 `SOL-05-A04-P13-P06-P02-P03`，不把 jsdom 当浏览器或 UAT 证据。

## 兼容与回滚

无数据升级。可移除前端面板/提交桥而不改既有 Review/结果史；已形成的 Review/Audit 不可删除。Gate 3、Pilot、正式三平台发行和真实客户确认仍未完成。
