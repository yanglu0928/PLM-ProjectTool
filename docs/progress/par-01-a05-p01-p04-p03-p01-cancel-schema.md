# PAR-01-A05-P01-P04-P03-P01 Parser 取消首响应版本表

日期 2026-09-30；Phase 2；结果 INTERNAL_PASS，非完整用户取消/Gate 通过。

编码前检查：WBS 仅解决 Parser 用户取消首次响应 `lock_version` 无持久来源的问题。输入冻结 API-03、CR-PAR-001、CR-PAR-002、已有 Jobs 取消历史/通用幂等和 Audit Export 专属快照；P04-P01/P02 内部取消已验。涉及 Jobs ORM、Alembic 0050 和隔离验证；实体为 `job_parse_cancel_versions`；不改公开 API，尚不授新权限。验收为空库及有数据升级、来源约束、历史不可变、非空降级拒绝、全量回归与 wheel；风险为错把专属 Audit 表混用或用当前版本冒充首次版本，故新增独立最小表，Owner 另项接线。

Changed/Files：新增 Jobs-owned 两列版本表和触发器，外键绑定 Audit 事件；只接受 PROJECT `document/DOCUMENT_PARSE` 的 USER 取消请求/终态检查事件，拒绝负版本、非法状态转移及 UPDATE/DELETE/TRUNCATE。新增 `CR-PAR-002`、Migration 合同/元数据/Schema 单测、`validation/par-01-a05-p01-p04-p03-p01-cancel-schema/verify.py`。未修改原 Gate 2 提交或旧迁移。

Migration：`20260930_0050`，上游 `0049`；Windows 11 隔离 PostgreSQL 18 验证空库 head→0049→head、已有 Project/User/Parser Job 的 0049→head→0049→head 保持原 Job 状态/版本，新表初始为空；有效事件 v2 可入，重复/负版本/畸形状态/更新/删除/清空均拒绝；已有快照时 downgrade 拒绝且 head 与历史保留。生产升级未执行，须备份停写；回旧代码可保表停入口，不删除历史。

API/权限/依赖：无公开 API 或权限变更，无新依赖。P02 将复核当前 Session/CSRF/License、创建者或 Project Manager、真实 Document 上传来源、同 UOW 取消/Audit/版本/幂等首响应并挂载现有 Job Cancel API。

Tests：Schema/Migration 定向5；后端全量 1632，3 项既有环境跳过，其余 PASS；隔离 PostgreSQL 验证脚本 PASS；开发 wheel 构建及包含 0050 PASS。PG 随机数据库已清理，PoC PG 已恢复停止。

Known Issues/Next：P01 没有用户主动取消能力；P02 Owner/HTTP、P03 过期与崩溃恢复、独立 Worker 进程、受权 Evidence/质量、三平台正式信任及可用程序包待。Gate 3 不变。
