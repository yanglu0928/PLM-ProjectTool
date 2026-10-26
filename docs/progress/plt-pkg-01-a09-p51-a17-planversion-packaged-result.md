# PLT-PKG-01-A09-P51-A17：候选构建完成，包内 PlanVersion 验收受阻

- 日期：2026-10-26
- 状态：`BLOCKED_FIXTURE_COMPOSITION`
- Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P51-A17`
- 源提交：`65a8598b4a03fd393749e1dc6a4dbacce3acde12`

## 已完成

- 基于固定 P45 父候选 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、固定 PoC pgvector wheel SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`、本提交构建的 backend wheel（SHA-256 `2b7f8e8e890be2cb2581c3f9db8b33f5f673e65719bc4b07889c2e4981fd5607`）与前端 dist 派生非发行候选。
- 候选：`artifacts/package-prep/windows11/current-app-p51-a17-20261026/output/current-app-candidate-301232ba36a5/NOT-FOR-RELEASE-windows11-current-app.zip`；SHA-256 `83ba6a6e2b838143b86cc6d633caa633feabc85387a8498cd73dc1aa48ef83f5`；22,246 payload files；manifest 绑定本源提交，`release_eligible=false`、`legal_clearance=false`。
- 前端源码相对 A02 已验证构建提交一致；本次重跑受到 Node 原生分配失败及 Windows 可提交虚拟内存不足影响，复用 A02 已验证、同一前端源码产出的 dist，未声称本轮构建再次通过。
- 候选已在两个唯一 D 盘路径完成清洁解包及固定摘要复核：`D:\PLM-Test-Temp\p51-a17-20261026\plm-current-app-stage-p51a17-301232ba` 和 `D:\PLMToolTemp\plm-current-app-stage-p51a17-301232ba`。
- P51 HTTPS/PG smoke 可启动候选 Python、Caddy/HTTPS、PostgreSQL 18，并通过 Handover、Evidence、Capability、Survey 等既有上游合成检查。

## 未通过/阻塞

- 包内运行的上游 P51-A05 Prototype Package 页面曾超时；经隔离验收驱动调整不再作为本次判据。
- PlanVersion fixture 阶段不存在已批准 Outline。复用源码 Outline fixture builder 需要当前 P51 HTTPS callback 未提供的 `port`、Runtime、License Guard、Audit、Session 及 Document/Download/Parse gateways；当前失败首先表现为缺少 `port`，因此尚未启动 PlanVersion 浏览器步骤。
- 这不是产品 API/Schema/运行时失败，也不证明 PlanVersion 包内流程失败或通过；缺口是隔离包验环境未接入 Approved Solution fixture。本次不伪造 Approved 来源，不绕过正式 Owner。
- 本 WBS 保持未完成。Pilot、Gate 3、正式发行仍为 `NOT_READY`。

## 环境异常及安全边界

- `pnpm build` 使用的预置 Node 崩溃；随后本机 Node 24 类型分析因 Windows 可提交虚拟内存仅约 0.9 GB 而 OOM。未修改 pagefile、未结束其他进程。
- 首次 stage 参数校验在创建目标前拒绝了非直接 Temp 子目录；随后在精确目标下成功。没有覆盖或删除历史 stage。
- 每次失败 smoke 后候选包和已验证 stage 保持原样；smoke runner 按自身 finally 停止并清理其拥有的服务/布局。用户 `.tmp/` 未改动。

## Changed / Files / Migration / API / Tests

- Changed：新增编码前检查及包验收 harness；未修改产品代码。
- Files：本记录、`validation/plt-pkg-01-a09-p51-a17-planversion-packaged/verify.py`、`run-edge-browser.mjs`、`STATUS.md`、`CHANGELOG.md`。
- Migration/API：无。
- Tests：Python `py_compile` 与 Node `--check` 通过；候选 manifest/inventory/hash 和清洁 stage 通过；上游包内合成检查通过。PlanVersion 包内 Edge/HTTPS/PG 旅程未到达，不能计 PASS。
- Result：`BLOCKED_FIXTURE_COMPOSITION`。
- Next：继续本 WBS，优先安全注入可审计的 Approved Outline 与关联服务 fixture，或把现有独立测试组合装配到包验 callback；之后重跑 PlanVersion HTTPS/Edge/PG、SQL、Secret、清理和远端同步验收。
