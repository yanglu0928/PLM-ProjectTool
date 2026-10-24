# PKG-PILOT-01-A01：当前应用非发行候选前置检查

日期：2026-10-24；状态：`NON_RELEASE_CANDIDATE_CLEAN_EXTRACT_PASS / PILOT_NOT_READY`。

|检查项|结果|
|---|---|
|当前 Phase / WBS|Phase 2 / `PKG-PILOT-01-A01`：当前源码 Windows 11 非发行候选重建与清洁解包预检|
|输入基线|Gate 2 冻结提交 `64cdf09`；CR-EXEC-002、CR-PKG-008、先行 CR-PKG-009；P45 父 ZIP 固定 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`|
|前置任务|P47-A02/A03 既有构建器与清洁解包工具；当前后端 wheel、前端 Vite 构建可在本机重新生成；正式信任装配仍阻塞 Pilot，不阻塞非发行预检|
|涉及模块|仅 `tools/` 非发行打包/验证，不修改产品运行模块|
|涉及实体 / API / 权限|均不变；不接触业务数据或客户资料|
|验收标准|接受真实哈希分块构建、拒绝额外/危险文件；全量父载荷/新包哈希；唯一新 ZIP、清洁解包与包内导入；保持所有不可发行标记|
|风险|用户 `.tmp/` 不能删除或打包；旧校验只认单 JS/CSS；大型新 ZIP 不能进 Git；正式公钥/法律/Gate 未通过|

本任务依据 CR-PKG-009 先记录再实施。若产物验收失败，仅标记前置/构建阻塞并转向独立任务，不伪称 Pilot 可用。

## 实测结果

- 干净源码提交：`0bb3ed2db7dae42dca449540a12239fcfe2a92eb`；已跟踪改动与除用户自有 `.tmp/` 外的未跟踪文件均为空。父 ZIP 重算 SHA 与固定值一致，旧包未修改。
- Python 3.13 后端 wheel 从此源码重建，SHA-256 `40367a33577b07792151d54426d1407baaa7e187d2a2651027c54fa4afc36cbb`；前端 `pnpm build`（含 typecheck）通过，`dist` 含 `index.html`、50 个 JS、36 个 CSS。
- 新包 `artifacts/package-prep/windows11/current-app-candidate-8ec4b6b0835d/NOT-FOR-RELEASE-windows11-current-app.zip`（本地 Git 忽略区，654,803,347 字节），SHA-256 `da90e98b41e8684a12af83c9d03a0162292cab9288e28c220dc38dfd72a4bb6a`。父包非应用载荷保留 20,573 件；新载荷 22,145 件；构建器逐件 SHA 和输出清单验证退出 0。`release_eligible=false`、`legal_clearance=false`、`formal_tls_material_included=false`。
- 在全新直接 ASCII Temp 目录 `C:\Users\17231\AppData\Local\Temp\plm-current-app-stage-f9b41cdeac8d` 独立清洁解包 22,145 件并全量读回哈希，退出 0。包内 Python `-I -B` 导入应用成功；包内 `0185` 迁移与源码 SHA 完全相同；前端 `index.html` 与重建 dist SHA 完全相同。定向构建器/暂存测试 5/5 通过。

Changed：非发行构建器接受严格哈希分块，保留来源脏检查与逐件完整性。Files：`tools/package_windows_current_app_candidate.py`、其定向测试、CR/决策/本证据/版本说明。Migration/API/权限：本任务无变更，候选仅携带既有 `0185`。Result：`NON_RELEASE_CANDIDATE_CLEAN_EXTRACT_PASS`。Known Issues：未运行包内 PostgreSQL 空/有数据升级、正式 HTTPS/License 启动、离线安装/重启/备份/升级或实际浏览器 UAT；正式公钥、法律结论、Gate 3～7 与三平台发行仍开放。Next：`PKG-PILOT-01-A02` 对此固定候选执行包内 PostgreSQL 18/pgvector 迁移预检；正式信任前置另线推进。
