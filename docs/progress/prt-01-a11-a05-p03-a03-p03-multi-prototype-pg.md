# PRT-01-A11-A05-P03-A03-P03：多个批准原型的Coverage并集

日期：2026-10-08。状态：`PRT_01_A11_A05_P03_A03_MULTI_PROTOTYPE_HTTP_PG_PASS`；Windows11隔离PG18.6/pgvector合成项目。

编码前检查：Phase2/Gate2冻结合同、`CR-PRT-005`和`DEC-20261008-1073`不变；P03-A03-P01/P02已证明单Link部分覆盖、目的不计数、跨项目和撤权失败关闭。本项只验证同一需求由两个正式Approved PrototypeVersion共同覆盖的现有规则，不改生产代码。风险是把多原型误判冲突或把重复覆盖误判完整；依据`DEC-20261008-1078`以全部验收标准的可计数并集验收。

一个正式批准Requirement包含两条验收标准；两个Prototype身份、Version、Review送审/客户角色合成批准和Trace均走正式服务，共用受权真实DocumentVersion。两条ACTIVE/VALIDATES Link起初都仅覆盖第一条验收标准，第二条标明未覆盖原因；Scope资格200，Coverage资格409。第二条Link经正式Supersede改为只覆盖第二条、第一条标明由首原型覆盖；两条当前Link的已覆盖并集完整后，HTTP预览返回两个PRT-03及一个REQ-03受审主体，两项Checklist PASS并进入SOLUTION/v13。文件被篡改时资格仍拒绝，预览后篡改仍不能写入Checklist。

运行迁移当前head且Alembic drift无新增操作；服务停机后未留本轮临时目录/端口。此为合成角色审批，不代表客户签署。兼容性/升级/回滚：只新增验证脚本、L2决策与进度/版本说明，无生产程序、Schema/API、权限、依赖或迁移；可撤脚本，业务历史不变。A03子项至此具备覆盖、混合、冲突、项目隔离和授权失效证据，但20并发、实际服务部署、生产信任源、Server2025、UAT与Gate3仍待。

TraceLink：`CR-PRT-005` → `DEC-20261008-1073/1078` → A05-P03-A03-P01/P02 → 本项多原型并集PG/HTTP证据 → A05-P04并发与生产入口。
