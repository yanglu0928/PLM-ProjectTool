# SOL-05-A03-P01：SectionVersion 历史读取授权前置

日期：2026-10-09。结果：`SECTION_VERSION_READ_POLICY_INTERNAL_PASS`；本项只增加尚未接线的 Project-owned 只读操作。

## 编码前检查

当前 Phase 2 Platform Core。输入 Gate2 冻结 API-04 的 `SOL_SECTION_VERSION_LIST/GET` 项目成员权限、CR-SOL-003、已验 P12 CREATE 与既有 Section/OutlineVersion 只读模式。涉及 Project 授权矩阵及其单元测试，不涉及 Schema、Migration、公开路径、生产数据或新依赖。验收标准是四类当前项目成员均可在锁定授权事实下执行两项只读操作，非成员统一隐藏；不因读策略存在而误称已开放历史读取。风险是未验当前权限就泄漏不可变历史，或把历史固定引用描述成现时来源资格。

新增 `SOL_SECTION_VERSION_LIST`、`SOL_SECTION_VERSION_GET` 两项 read policy：四类项目成员、`lock_reads=True`，不附加目标资源授权。具体 Section/Version 的同项目身份与根/版本一致性必须由后续 A03 Owner 查询证明；单靠当前成员策略不能推定可见。授权矩阵定向测试 10 通过、772 子测试；后端全量 3537 通过、3 跳过、5549 子测试通过。后续 A03-P02 内部 GET/LIST 读取 Owner，须定义冻结路径的安全元数据、固定引用投影与父指针一致性；A03-P03 独立游标和 HTTP；A03-P04 Windows/PG；A03-P05 UI/Edge。任何新增冻结合同细节先记录增量设计，不破坏 `/api/v1`。

兼容/回滚：无 Schema/API/旧数据/依赖变化；撤两项未接线策略和对应测试可回滚。正式 HTTPS/账户/公钥、Server2025、Gate3/UAT/发行尚未验，Debian13 实机依用户指令跳过。TraceLink：Gate2 API-04 → CR-SOL-003 → P12 CREATE → 本 A03-P01 → A03-P02 历史 Owner。
