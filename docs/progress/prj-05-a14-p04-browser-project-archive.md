# PRJ-05-A14-P04：项目归档 Windows 11 浏览器与隔离数据库验收

- 日期/阶段：2026-09-29 / Phase 2；结果：PASS（Windows 11 本机合成端到端，非正式信任或三平台验收）。输入为 P01～P03、后端归档合同及 DEC-20260929-468。
- Changed/Files：`validation/prj-05-a04-browser-project/serve.py` 增加互斥 `--archive-api-only`、`--archive-browser` 模式，只操作每轮随机数据库内的合成项目；本进度、决策、版本、状态同步。无生产程序、API、Schema、Migration、权限或依赖变化；回滚可撤夹具新增模式。
- HTTP：匿名 401、非负责人 404、缺 CSRF 403、外项目 404、缺 If-Match 428；首次归档 200/`"v1"`、同 Key 同结果重放 200、同 Key 异版本冲突 409，独立详情读取 ARCHIVED/v1。API-only 完整运行 exit0。
- Browser：实际 IAB 从“我的项目”进入 OWNED 项目详情，只有当前负责人可见的归档入口先提示单向影响与后续禁止新写/任务，明确勾选后提交；首次回执标明非当前状态证明，独立刷新后显示已归档且无再归档入口。browser fixture 完整运行 exit0。
- Database/cleanup：两轮 SQL 均核 OWNED `ARCHIVED/v1`、FOREIGN `ACTIVE/v0`、负责人仍有效、恰一 `PROJECT_ARCHIVED` Audit 与完成收据；随机数据库、角色、Vault 精确清理 exit0。PoC PG 测试前停止，启动时提示可能已有进程但成功启动；结束核实际运行并用 fast stop 正常恢复停止。旧 PID 提示原因未证实。
- Tests/compatibility/upgrade：两个隔离模式各完整运行一次，Python 语法检查通过；本项未重跑前端全量测试，P03 已有 720/720、typecheck、build PASS。兼容 DB head `20260927_0049` 与冻结 `/api/v1`，无升级步骤。
- Known Issues/Next：仅合成信任源与 Windows 11；正式 TLS/可信时钟、Server 2025/Debian、性能、POC-03 AI 质量、Gate3/可用包未验。下一项按 Phase 2 WBS 处理项目名称更新前端合同，独立核对冻结 `PROJECT_PATCH` 后再编码。
