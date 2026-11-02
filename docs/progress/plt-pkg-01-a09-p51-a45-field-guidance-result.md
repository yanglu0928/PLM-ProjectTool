# PLT-PKG-01-A09-P51-A45：就绪报告逐字段填写指引

- 日期：2026-11-02
- 状态：PASS_LIMITED
- 执行环境：GitHub hosted Windows Server 2025（Azure，D:\ runner temp）；本机未运行程序。
- 来源提交：PR #61 合并候选 `671d2c7cb0fb833bb2f3be7a0266c46dd352fb65`
- Workflow：[41378263123](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41378263123)，12/12 jobs 成功。

## 变更

扩展父包内只读 readiness JSON。对登记表每一个缺失键返回固定中文指引，说明需维护的引用/摘要类型、建议证据来源和禁止输入内容。提示只从静态字段字典生成，并按实际缺项筛选；不拼入登记值、路径、客户材料或秘密。完整登记时提示为空，但状态仍要求独立核验，不授权启动或发行。包内清单与逐文件摘要保持不变。

## 云端验收证据

- 单元测试验证 9 个缺失字段均有且仅有相应 `label/maintain/source/never` 指引；完整登记返回空指引并保持 `launch_authorized=false`。
- 同run父包清洁解包与临时 PostgreSQL 18.6/pgvector 0.8.6 smoke 成功。ZIP SHA-256：`e2858a6b6af852ada906e84671b539dee25c2571387940e4680346dd2c0256ca`；payload 20,122 files。
- readiness smoke：9 项缺失正确检测、完整登记不授权、无效值不回显、package manifest 不变。
- A17：合成 PlanVersion Edge/HTTPS/PG 流程 29 次 API；状态 `IN_REVIEW`，WBS/requirement/validation=(2,2,1)，customer decisions=0；证据仅为合成数据。
- A34：隔离包替换、失败候选隔离及显式手动恢复均通过；现有数据标记与 provenance 保留。
- 同run父候选artifact ID `13112760321`，外层artifact SHA-256 `59ad489ef9647d266773411e15d6837aa1c3c5b8a4ff64867204bdb37b78472b`，372,791,674 bytes，保留至 2026-11-16。

## 偏差记录

A45 前置文件已记录本次范围/回滚/安全边界。Hosted merge-run 使用 PR 合并提交，而构建源码 head 为 `f106609515ec59032d188e5a4a3c452561287cba`；所有制品均从该run的合并候选内同一源码和上游固定依赖重建，记录最终合并提交作为证据源，不把本机未运行描述成 Windows 11 实测。

## 兼容性与限制

这是父包操作区诊断 JSON 的向后兼容增量；不改 API/Schema/Migration、安装或启动路径。只证明 hosted Windows Server 2025 行为，不能推定 Windows 11 新运行兼容。没有安装程序、服务/API/监听器启动或生产数据操作。

正式公钥/License trust、数据库凭据身份、服务账户 ACL、TLS 证书和法律放行仍缺失；`Pilot`、Gate 3 和正式 Release 继续 `NOT_READY`。本结果不构成 Gate、客户确认或发行许可。
