# PLT-PKG-01-A09-P51-A17：候选构建完成，包内 PlanVersion 验收受阻

- 日期：2026-10-26
- 状态：`BLOCKED_MISSING_APPROVED_SECTION_FIXTURE`
- Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P51-A17`
- 源提交：`65a8598b4a03fd393749e1dc6a4dbacce3acde12`

## 已完成

- 基于固定 P45 父候选 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、固定 PoC pgvector wheel SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`、本提交构建的 backend wheel（SHA-256 `2b7f8e8e890be2cb2581c3f9db8b33f5f673e65719bc4b07889c2e4981fd5607`）与前端 dist 派生非发行候选。
- 候选：`artifacts/package-prep/windows11/current-app-p51-a17-20261026/output/current-app-candidate-301232ba36a5/NOT-FOR-RELEASE-windows11-current-app.zip`；SHA-256 `83ba6a6e2b838143b86cc6d633caa633feabc85387a8498cd73dc1aa48ef83f5`；22,246 payload files；manifest 绑定本源提交，`release_eligible=false`、`legal_clearance=false`。
- 前端源码相对 A02 已验证构建提交一致；本次重跑受到 Node 原生分配失败及 Windows 可提交虚拟内存不足影响，复用 A02 已验证、同一前端源码产出的 dist，未声称本轮构建再次通过。
- 候选已在两个唯一 D 盘路径完成清洁解包及固定摘要复核：`D:\PLM-Test-Temp\p51-a17-20261026\plm-current-app-stage-p51a17-301232ba` 和 `D:\PLMToolTemp\plm-current-app-stage-p51a17-301232ba`。
- P51 HTTPS/PG smoke 可启动候选 Python、Caddy/HTTPS、PostgreSQL 18，并通过 Handover、Evidence、Capability、Survey 等既有上游合成检查。

## 最新续行结果（2026-10-26）

- 已按 `DEC-20261026-P51-A17-packaged-fixture-context.md` 将 PG 端口、数据库名、API 数据根和本次合成公钥定位附着于 smoke 的 `fixture_db` 能力，避免扩展多层 callback kwargs；真实 License Guard、Audit、Document/Download/ParseResult 组件组合成功。
- 清洁 stage 仅从 `D:\PLM-Test-Temp\p51-a17-20261026\plm-current-app-stage-p51a17-301232ba` 只读核验后复制到新的 `D:\PLM-Test-Temp\p51-a17-20261026\PLMToolTemp\plm-current-app-stage-p51a17-retry-20261026`；22,246/22,246 文件与摘要一致。运行时使用 `-B`，该 stage 未出现额外 pyc。
- 新 harness 多次启动包内 PostgreSQL 18/HTTPS，Handover、Evidence、Capability、Survey 既有合成前置链均有通过证据；复用 Outline source fixture 时确认随机数据库需绑定正确数据库名，已修正。
- **当前实际阻塞**：本次合成项目不存在 `sol_section_versions` 对应的已批准 Section 来源，既有包内前置 Handover/Survey 不会生成 SOL Section。业务 Outline Owner fixture 依赖已有批准 Section；因此尚未能构造 Approved Outline，A17 PlanVersion Edge 浏览器旅程仍未启动。未直接 SQL 伪造批准，也未绕过 Owner。
- 包内重复运行出现两类无关旧验收噪声：一轮 Evidence Edge target 启动超时，另一轮 Survey Edge 清理临时 Chromium Profile 时 EBUSY。没有把它们判为 A17 产品失败；从 A17 smoke 的 post-review 无关 Survey 驱动中隔离，明确见 DEC。
- 首次依赖探测曾在旧 D 盘 stage 生成 `__pycache__`，完整性检查正确拒绝；该旧 stage保留为失败调试副本，不作为验收输入。之后使用干净复制 stage。候选 ZIP未修改，SHA仍需在最终验收末次复核。

## 未通过/阻塞

- 包内运行的上游 P51-A05 Prototype Package 页面曾超时；经隔离验收驱动调整不再作为本次判据。
- 这不是 PlanVersion 产品 API/Schema/运行时失败；包内 PlanVersion Edge/HTTPS/PG结果为未验，不能记 PASS 或 FAIL。阻塞是当前隔离项目缺少由 SOL Owner/Review Owner 形成的合成 Approved Section 来源。
- 本 WBS 保持未完成。Pilot、Gate 3、正式发行仍为 `NOT_READY`。

## 环境异常及安全边界

- `pnpm build` 使用的预置 Node 崩溃；随后本机 Node 24 类型分析因 Windows 可提交虚拟内存仅约 0.9 GB 而 OOM。未修改 pagefile、未结束其他进程。
- 首次 stage 参数校验在创建目标前拒绝了非直接 Temp 子目录；随后在精确目标下成功。没有覆盖或删除历史 stage。
- 每次失败 smoke 后候选包和已验证 stage 保持原样；smoke runner 按自身 finally 停止并清理其拥有的服务/布局。用户 `.tmp/` 未改动。

## Changed / Files / Migration / API / Tests

- Changed：新增编码前检查及包验收 harness；未修改产品代码。
- Files：本记录、`docs/changes/DEC-20261026-P51-A17-packaged-fixture-context.md`、`validation/plt-pkg-01-a09-p51-a17-planversion-packaged/verify.py`、`run-edge-browser.mjs`、`tools/smoke_packaged_platform_write_https.py`、`tools/smoke_current_app_packaged_https.py`、`STATUS.md`、`CHANGELOG.md`。
- Migration/API：无。
- Tests：AST语法与 `git diff --check` 通过；候选既有 manifest/inventory/hash证据保持有效；本轮 package chain上游多项通过但总 smoke受上述来源缺失/旧Edge不稳定未退出0。PlanVersion浏览器步骤未启动。
- Result：`BLOCKED_MISSING_APPROVED_SECTION_FIXTURE`。
- Next：先以 SOL Section Create/Review Owner 在同一 disposable PG中建立清楚标注的合成批准来源，再运行 Outline Owner；不得将直接数据库插入状态作为 Approved 证据。然后完成 PlanVersion Edge/HTTPS/PG、SQL、Secret、清理和远端同步验收。
