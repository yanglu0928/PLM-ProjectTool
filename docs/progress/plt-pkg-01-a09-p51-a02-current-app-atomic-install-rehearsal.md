# PLT-PKG-01-A09-P51-A02：当前应用候选原子落地隔离演练

日期：2026-10-25；状态：`NON_RELEASE_CURRENT_APP_ATOMIC_PLACEMENT_PASS`；变更依据：`CR-PKG-011`。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；当前 WBS：`PLT-PKG-01-A09-P51-A02`。
- 输入基线：P47 当前应用 `WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE` 清单/哈希结构、P39 私有 staging→逐件复制和读回→同卷原子 rename 失败关闭模式、CR-PKG-011。
- 前置任务：P51-A01 已确认正式启动缺产品公钥而阻塞，并按 A06-P02 转向非发行安装链；CR-PKG-011 已先行记录旧 P39 工具绑定旧候选种类的兼容差异与所选方案。
- 涉及模块：新增 Windows 当前应用候选的开发/验收演练工具及独立测试；不修改旧 P39 实现。
- 涉及实体/API/权限：无业务实体、API、数据库、权限或 License 行为变化；没有实体服务器、无数据库启动、无 SCM/防火墙/证书改动。
- 验收标准：只接受调用方固定的当前应用非发行候选 SHA、其manifest类型/发行禁用标志和全量 payload 清单；源暂存区需来自既有独立清洁提取验证；目标为全新 ASCII Temp 直属根；目标文件集与源逐件一致、哈希全量读回后才原子发布；已有目标、正式 `C:\PLMTool`、路径逃逸、链接、哈希错配必须拒绝；复制故障只能清理本次工具拥有的私有部分目录，ZIP SHA 前后不变。
- 风险：仅证明候选的隔离文件落地与完整性，不代表真正服务启动、正式信任、应用可用、Pilot或发行通过。临时空间不足或强杀可能留下未发布的私有待恢复目录；不自动清理未知项。
- 预计修改文件：`tools/install_windows_current_app_candidate_rehearsal.py`、对应 `tools/tests/` 测试、进度/状态/版本说明与 CR 验收结果。

## 实施与单元验收

- 新增与 P39 独立的当前应用候选演练器：读取当前 candidate kind、不可发行标志及 checksum manifest；与既有清洁 stage 逐件重验；只映射到 `target/app/<payload-relative-path>` 并创建空 `plugins/data/logs/license/runtime` 根目录；复制写后 fsync、逐件读回与全集检查后同卷 rename。
- 明确结果标记 `formal_install_performed=false`、`services_changed=false`、`database_started=false`、`release_eligible=false`。旧 P39 工具及 P33 固定验收未修改。
- 定向测试：5 passed，覆盖映射、非 payload/Windows 大小写冲突拒绝、隔离原子落地/哈希与非发行标志、注入复制中断后目标不存在且私有临时目录清除、已有目标保留并拒绝。第一轮调用系统 Python 因未安装 pytest 无法收集；切换项目既有 Python 3.13 环境后测试通过；没有断言失败。
- 在候选实测开始前，状态为实现及单测已通过、干净候选复验待执行；实际候选验收结果见下节。此工具不启动应用、PG 或 Caddy；实际包内运行/UAT另项验证。

## Windows 11 当前候选验收

- 源 HEAD：`c2ec928a4c67007c05bf7de18dbfb6d8bab95ac6`；基于固定父候选 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，使用后端 wheel SHA `4272382b385bb21750f316986043447142b7611290ddf8af689a4b2eb166ace8`、pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f` 和本提交重新构建的前端 dist 派生新候选。
- 新候选：`artifacts/package-prep/windows11/current-app-p51-a02-20261025/output/current-app-candidate-96313d4e1215/NOT-FOR-RELEASE-windows11-current-app.zip`，654,939,007 bytes，SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`，22,197 payload files；`release_eligible=false`、`legal_clearance=false`。候选从最新已推送干净提交 `c2ec928a` 生成；失败的首次构建调用误传8位短SHA，被CLI拒绝，改传完整40位HEAD后成功，无构建输入被改动。
- 清洁提取到 `D:\PLMToolTemp\plm-current-app-stage-p51a02-96313d4e`，逐项校验后独立复核输出 `NON_RELEASE_CURRENT_APP_CLEAN_EXTRACT_PASS`，来源提交与候选SHA相同。
- 原子文件落地到 `D:\PLMToolTemp\plm-current-app-install-p51a02-96313d4e`，输出 `NON_RELEASE_CURRENT_APP_ATOMIC_PLACEMENT_PASS`、22,197 files 和 mapping SHA-256 `3e23900fcb9b2087117ed46c209480344187ae31fa001fbead785d90f090977a`。独立外层复核确认目标文件数22,197、预期空目录存在、候选 SHA 仍为 `3cbd68aa…f2326f455`、临时私有 partial 已消失。
- 未启动任何产品应用、PostgreSQL、Caddy 或 SCM 服务；正式根未使用。Stage 与目标安装演练布局暂留在 D 盘隔离 Temp 根供下一独立包内启动前置复核，确认不需后续测试后再按精确路径清理；不触碰用户 `.tmp/`。
- 本项只证明当前非发行候选的安全文件原子落地与完整性；不证明离线启动、可用安装、正式信任/License、真实客户链、Pilot、Gate或发行通过。
