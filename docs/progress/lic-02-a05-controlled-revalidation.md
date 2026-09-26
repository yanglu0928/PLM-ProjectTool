# LIC-02-A05：受控重验证与状态恢复

- 日期：2026-09-24；结果：PASS（仅内部命令）；依据：Gate 2、ADR-006、DM-02、API-02、CR-LIC-001、DEC-20260924-094。
- Changed：DeploymentAdmin 的有效 Session/CSRF 才能触发 ACTIVE 安装重验证；核对不可变文档摘要、当前事件/状态一致性，重新使用现有 LicenseService 检查受信任公钥、Ed25519、选定机器、有效期和可信时间。只有完整通过恢复 VALID；失败写分类拒绝事件和状态。安装验证引用、状态和 Audit 在单事务提交，审计失败回滚。拒绝状态不能由普通 Guard 自行恢复。
- Files：`revalidation.py`、`revalidation_repository.py`、`test_license_revalidation.py`、`validation/lic-02-a05-revalidation/verify.py`、状态/决策/版本文档。Migration：无。API：无公开路由。Permission：Auth 所有的 DeploymentAdmin Session+CSRF 适配器。
- Tests：Windows 11/Python 3.13 后端 182/182 PASS；服务单元覆盖率 93%；PostgreSQL 18.6 临时库真实合成 Ed25519 恢复、CSRF 拒绝、过期/可信时间拒绝及审计回滚 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：临时库使用进程内合成公钥与可信时间替身，不等于生产密钥来源/完整性初始化验收；可信时间前移与结果记录分属事务，后者失败时本次恢复拒绝。尚无公开 HTTP 路由、幂等层、生产公钥/选定 MAC/可信时间密钥来源和初始化；性能、Gate 3/UAT 未验收。
- Next：`LIC-03-A03 生产可信来源与初始化装配`，编码前核对具体 WBS 边界。
