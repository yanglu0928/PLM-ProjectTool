# SOL-01-A04-P07-P01：Reference 固定文档定位身份

日期：2026-10-09；结果：`REFERENCE_DOCUMENT_LOCATION_BACKEND_PASS`，限定 Windows 11 隔离 PostgreSQL 18.6/合成 License/私有文件。

编码前检查：Phase 2 Platform Core；WBS 为 P07-P01；输入为冻结 API-04、既有 PROJECT Reference GET 与 Document/Evidence 详情接口；前置 P04-P01～P06 已通过。涉及 Solution 读取投影及 Document 根/版本身份，不变更实体 Schema、权限或路径；同项目有效成员与 License 校验保持原样。验收是固定版本可定位根 ID、错配/跨项目/混源失败关闭、原字段和响应合同保持兼容。主要风险是历史固定引用不证明当前来源可访问，详情仍须独立鉴权。

按先登记的 `CR-SOL-008`，PROJECT Reference GET 增加有序 `document_refs[]`，每项只含 `document_id` 和 `document_version_id`，保留 `document_version_ids[]`。仓储同事务联结 DocumentVersion/Document，检查根和版本均为请求项目的 PROJECT 来源；应用层检查新旧数组一一对应。EvidenceId 仍由独立 Viewer 定位。无新 API、Schema、Migration 或依赖；客户端尚未接线。

验证：定向单元/API 合同 8 通过、26 子例；三条隔离 PG 验证（Owner、真实 Session/HTTP、Windows 显式组合）均退出 0，并从真实版本表对照根 ID、验证越权/异常来源拒绝；后端全量 `3322 passed, 3 skipped, 4906 subtests passed`。已知问题：前端点击定位、浏览器 UAT、正式 License/目标账户、Server 2025、20 并发及 Gate 3/发行尚未验证。Debian 13 按用户指令跳过。回滚为关闭该增量投影/前端入口，历史数据与旧字段不变。

TraceLink：冻结 API-04 → P04-P01～P03 GET → CR-SOL-008 → P07-P01 → 单元/合同/PG/全量回归。
