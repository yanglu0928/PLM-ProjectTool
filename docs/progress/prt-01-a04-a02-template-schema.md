# PRT-01-A04-A02：PrototypeTemplate Schema0127

日期：2026-10-08。结论：`PRT_01_A04_A02_TEMPLATE_SCHEMA_PASS`。下一项：
`PRT-01-A04-A03` PROJECT/GLOBAL Template Create Owner。

## 实施结果

- 新增 M-SCP `prt_templates`，固定 GLOBAL/PROJECT 与 ProjectId 二元关系，保存名称、状态、当前不可变
  TemplateVersion 指针、创建/更新事实和乐观锁。
- 新增 V-SCP `prt_template_versions`，固定版本号、PUBLISHED状态、32字节内容指纹、同Template前版、
  JSONB布局/组件合同、1～16个适用终端和创建事实。Root当前指针使用
  `(current_template_version_ref, prototype_template_id)` 复合延迟FK，禁止指向其他Template版本。
- 新增有序 `prt_template_artifact_refs`，只接受 DOCUMENT_VERSION/OUTPUT_ARTIFACT固定目标并在版本内按
  ordinal和目标去重；不建立多态跨模块共享写FK，后续Owner通过目标Application Port证明。
- 新增 `prt_template_command_results` 供CREATE/REVISE持久结果使用。A03前四表所有行级写入失败关闭，
  TRUNCATE永久拒绝；空历史可降0126，任何Template历史拒绝破坏性降级。

## 验证证据

- Windows 11/PostgreSQL 18.6一次性库：0126已有User/Project升级保留、0127空历史降级/重升、Alembic
  drift、Owner关闭、Scope/JSON对象约束、TRUNCATE拒绝和有历史拒降通过；标志
  `PRT_01_A04_A02_TEMPLATE_SCHEMA_PASS`。
- 首次实库drift虽通过但报告新Root/Version循环排序警告；将Root指针改为复合延迟FK并在ORM设置
  `use_alter`，完整复跑后该新警告消失。既有RAG operator class/计算列提示仍属历史提示，不冒充本项缺陷。
- Schema/metadata/migration定向17项通过；完整后端3114项通过、3项跳过；compileall通过。
- 开发wheel共1185项，SHA-256
  `b39bc65e1fa9d7ae1fae343082eb1d687e197c1e68b25340bcf29d75ae693c84`。
- 首次从仓库根错误使用 `unittest discover -s apps/backend/tests/unit`，38个包内相对导入失败；该运行无效且
  未计为产品失败/通过。按既有中文路径方法在 `apps/backend` 目录运行 `discover -s tests` 后全量通过。

## 兼容、回滚与未完成

只增加内部Schema/ORM和验证，不改变冻结HTTP、依赖、Secret、外发、License或执行边界。Root/Version
双向关系通过延迟FK支持同事务创建；Owner仍关闭，所以本项不形成可用Template。停止后续装配即可回滚
运行入口；空历史可物理降级，存在历史只允许前向修复。A03 Create、A04 Revise、A05 Read、A09 HTTP、
Windows Server 2025、Gate 3/UAT/发行仍待；Debian 13按用户指令跳过。
