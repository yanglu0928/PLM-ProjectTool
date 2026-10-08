# PRT-01-A11-A05-P03-A01：批准原型单需求分支真实验收

日期：2026-10-08。状态：`PRT_01_A11_A05_P03_A01_APPROVED_HTTP_PG_PASS`；仅一条已批准Requirement完全由一条Approved PrototypeVersion覆盖，不代表混合范围或完整A05通过。

编码前检查：Phase 2/Gate 2冻结合同；前置Requirement真实顺序链、Prototype Owner/Workflow可选装配、Document物理证明、P02全NOT_REQUIRED链均已验。当前任务只验证Approved PrototypeVersion→有效Link→Checklist→SOLUTION；涉及Prototype、Requirement、Review、Trace、Document、Workflow，沿用ProjectManager发起、CustomerManager合成审批，正常生产入口仍关闭。无Schema、API、权限或依赖变更。风险为把送审当批准、把Link当全部覆盖、只看Document元数据；以正式Review Owner及磁盘本体重证约束。

隔离脚本复用Requirement→PROTOTYPE/v10实测前置；仅模板和Document固定文件的测试输入使用显式合成数据，其余Prototype创建、Version创建、Review送审/客户角色审批、批准Trace、Link创建均经正式Application Service。先证明批准Version但缺Link时`PROTOTYPE_SCOPE_DECISIONS`可预览、`PROTOTYPE_COVERAGE`拒绝；补足唯一验收标准的ACTIVE/VALIDATES Link后，篡改磁盘字节会令两项资格均拒绝。恢复字节后，HTTP返回有序`PRT-03`/`REQ-03`受审主体及真实来源Evidence，两项Checklist按强ETag登记PASS，PROTOTYPE→SOLUTION/v13成功。Alembic当前head迁移与drift检查通过，已知向量表达式/计算默认值比较警告仍在；实例与临时目录清理后未留本轮监听端口。

兼容性/升级/回滚：仅增加验证资产并为Requirement验收回调暴露已有Reviewer测试上下文；不改生产程序、Schema、冻结API、权限或依赖，无升级步骤。可移除本脚本且既有业务历史不变。生产Prototype路由/页面继续关闭。下一步P03-A02验证多需求混合NOT_REQUIRED/Approved Prototype覆盖与遗漏/冲突/漂移，随后20并发、目标平台与正式生产入口证据。Gate 3仍BLOCKED。

TraceLink：`CR-PRT-005` → A11-A03真实Owner/Document证明 → A05-P01物理文件 → A05-P02全NOT_REQUIRED → 本项已批准原型单需求分支 → P03-A02混合范围。
