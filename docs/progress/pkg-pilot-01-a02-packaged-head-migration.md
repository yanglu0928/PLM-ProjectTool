# PKG-PILOT-01-A02：当前候选随包数据库迁移前置检查

日期：2026-10-24；状态：`NON_RELEASE_PACKAGED_PG18_0185_MIGRATION_PASS / PILOT_NOT_READY`。

|检查项|结果|
|---|---|
|当前 Phase / WBS|Phase 2 / `PKG-PILOT-01-A02`：固定 A01 候选的包内 PostgreSQL 18/pgvector `0184→0185` 迁移预检|
|输入基线|Gate 2/CR-PKG-008/CR-PKG-009；A01 非发行 ZIP SHA `da90e98b41e8684a12af83c9d03a0162292cab9288e28c220dc38dfd72a4bb6a` 与独立清洁暂存；当前迁移 `20261024_0185`|
|前置任务|A01 候选完整性/解包/导入通过；旧 P47-A04 临时库演练工具仅支持 `0051→0052`，不可据此声称最新迁移已验|
|涉及模块|仅非发行包迁移烟测工具；使用包内 Python、PG18/pgvector 与现有 Alembic，不改产品数据库代码|
|涉及实体|合成 `plt_system_configurations` 旧行；检查新增 `sol_outline_review_state_results` 与闭合 Trigger|
|涉及 API / 权限|无；不使用正式服务账户或真实客户数据|
|验收标准|一次性隔离 PG 集群中有数据 `0184→0185→0184→0185`、空库直升、旧行保留、新表/触发器存在、pgvector 可用、停止并清理临时集群|
|风险|迁移规模大、失败后临时库残留；仅使用新随机回环端口和直接 Temp 子目录，绝不指向既有数据库；正式安装/升级另验|

本片只验证当前候选随包迁移，不关闭正式 Pilot、客户数据升级或三平台发行。

## 先失败、修复与实测结果

原 A01 候选 SHA `da90e98b41e8684a12af83c9d03a0162292cab9288e28c220dc38dfd72a4bb6a` 在包内 Alembic 导入 RAG ORM 时退出 1：缺 Python `pgvector`。候选完整性 PASS 不等于运行时依赖齐全；当次一次性 PG 已停止并清理。后端 wheel 的 19 项依赖与包内 dist-info 核对仅缺此一项。依 [CR-PKG-010](../changes/CR-PKG-010-python-pgvector-runtime-gap.md) 从固定 PoC wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f` 向新候选补入 46 件 Python 包与 MIT 许可，第三方清单标记待法律审阅，不改父包或 A01 ZIP。

干净源码提交 `98d28da3498deefafbfa4396fda6fea16743d136` 重建后端 wheel SHA `38d85de1afe0c983f84a67efb7ea13cb52e62f6b86b2c382ebc23eec54a1cf37` 及前端 typecheck/build。新 ZIP `artifacts/package-prep/windows11/current-app-candidate-2c08715872fd/NOT-FOR-RELEASE-windows11-current-app.zip`，654,841,707 字节，SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d`；父包非应用载荷 20,573 件保留，输出 22,191 件逐项 SHA 验真，`release_eligible=false`、`legal_clearance=false`。全新直接 ASCII Temp 暂存 `C:\Users\17231\AppData\Local\Temp\plm-current-app-stage-7d7117dd964c` 完整清洁解包/独立读回退出 0；包内 Python `-I -B` 导入 `pgvector==0.5.0` 和应用成功。

包内 Python、PostgreSQL 18 和服务器 pgvector 0.8.6 在一次性随机回环端口集群演练：有数据 `20261023_0184→20261024_0185→20261023_0184→20261024_0185`；旧合成配置行始终为 1；新 Outline Review 结果表、闭合触发器及唯一索引存在；第二个空库直接升至 `0185`。脚本退出 0，临时 PG 停止/数据目录清理，既有库未触碰。定向打包、暂存、迁移边界 8/8 通过。

Changed：补固定 Python pgvector wheel 的非发行派生与当前头迁移演练模式。Files：打包/迁移工具及测试、CR/决策/本记录/版本说明。Migration/API/权限：本任务无产品变更，候选验证既有 `0185`。Result：`NON_RELEASE_PACKAGED_PG18_0185_MIGRATION_PASS`。Known Issues：没有真实客户历史升级、正式服务账户/公钥/HTTPS 启动、离线安装/重启/备份/升级、法律放行、完整 UAT/性能或三平台验收。Next：`PKG-PILOT-01-A03` 同一固定候选的隔离 HTTPS/License 失败关闭和当前业务路由冒烟；正式信任前置另线保持阻塞。
