# PLT-PKG-01-A09-P51-A17：包内 PlanVersion 纵向验收通过（范围限定）

- 日期：2026-10-26
- 状态：`PASS_SCOPE_LIMITED`
- Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P51-A17`
- 最终源提交：`f66bc60bf320288413db17868d79223d25f69ec5`

## 初始候选构建（已由最终候选替代）

- 基于固定 P45 父候选 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、固定 PoC pgvector wheel SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`、本提交构建的 backend wheel（SHA-256 `2b7f8e8e890be2cb2581c3f9db8b33f5f673e65719bc4b07889c2e4981fd5607`）与前端 dist 派生非发行候选。
- 候选：`artifacts/package-prep/windows11/current-app-p51-a17-20261026/output/current-app-candidate-301232ba36a5/NOT-FOR-RELEASE-windows11-current-app.zip`；SHA-256 `83ba6a6e2b838143b86cc6d633caa633feabc85387a8498cd73dc1aa48ef83f5`；22,246 payload files；manifest 绑定本源提交，`release_eligible=false`、`legal_clearance=false`。
- 前端源码相对 A02 已验证构建提交一致；本次重跑受到 Node 原生分配失败及 Windows 可提交虚拟内存不足影响，复用 A02 已验证、同一前端源码产出的 dist，未声称本轮构建再次通过。
- 候选已在两个唯一 D 盘路径完成清洁解包及固定摘要复核：`D:\PLM-Test-Temp\p51-a17-20261026\plm-current-app-stage-p51a17-301232ba` 和 `D:\PLMToolTemp\plm-current-app-stage-p51a17-301232ba`。
- P51 HTTPS/PG smoke 可启动候选 Python、Caddy/HTTPS、PostgreSQL 18，并通过 Handover、Evidence、Capability、Survey 等既有上游合成检查。

## 中间续行记录（截至最终复验前；历史失败已由下文最终复验覆盖）

- 已按 `DEC-20261026-P51-A17-packaged-fixture-context.md` 将 PG 端口、数据库名、API 数据根和本次合成公钥定位附着于 smoke 的 `fixture_db` 能力，避免扩展多层 callback kwargs；真实 License Guard、Audit、Document/Download/ParseResult 组件组合成功。
- 清洁 stage 仅从 `D:\PLM-Test-Temp\p51-a17-20261026\plm-current-app-stage-p51a17-301232ba` 只读核验后复制到新的 `D:\PLM-Test-Temp\p51-a17-20261026\PLMToolTemp\plm-current-app-stage-p51a17-retry-20261026`；22,246/22,246 文件与摘要一致。运行时使用 `-B`，该 stage 未出现额外 pyc。
- 新 harness 多次启动包内 PostgreSQL 18/HTTPS，Handover、Evidence、Capability、Survey 既有合成前置链均有通过证据；复用 Outline source fixture 时确认随机数据库需绑定正确数据库名，已修正。
- **当前实际阻塞**：A17 的真实 SOL Section/Review Owner 夹具尚未能运行到建立 Section；此前因 observer 与 manager Session proof 配对错误触发 `AUTH_ACCESS_DENIED`。修复已实施但未实测。随后遇到 C 盘极低空间，不能安全重跑完整 packaged smoke；PlanVersion Edge 浏览器旅程未启动。未直接 SQL 伪造批准，也未绕过 Owner。
- 包内重复运行出现两类无关旧验收噪声：一轮 Evidence Edge target 启动超时，另一轮 Survey Edge 清理临时 Chromium Profile 时 EBUSY。没有把它们判为 A17 产品失败；从 A17 smoke 的 post-review 无关 Survey 驱动中隔离，明确见 DEC。
- 首次依赖探测曾在旧 D 盘 stage 生成 `__pycache__`，完整性检查正确拒绝；该旧 stage保留为失败调试副本，不作为验收输入。之后使用干净复制 stage。候选 ZIP未修改，SHA仍需在最终验收末次复核。
- 本轮复验发现底层包烟测依赖进程默认 `tempfile` 路径，已改为显式 `PLM_TEST_TEMP_ROOT` 并强制 D 盘 `PLMToolTemp`，stderr 仅落在本轮 D 盘 run 内且只投影安全摘要；另对 health readiness 超时附最近状态码/无响应结论。AST 与差异空白检查通过。
- 一份既有直接 D 盘 stage 多 646 个非清洁额外文件，被前置校验拒绝且未作为验收输入。改用此前记录的清洁 stage，新建 D 盘副本总清单 22,249 件；候选包内上游 Edge/PG 链通过，进入 `_approved_section_fixture` 后在 Outline Create Owner 被 `AUTH_ACCESS_DENIED` 拒绝。
- 已定位为上游 Handover Review 验收器把共享 client 留在 observer 身份，造成夹具误将 observer cookie 与 manager CSRF 配对。已改为通过包内正式 Login HTTP 获取 manager Session，并断言 `data.user.user_id` 与 manager UUID 一致；最新修正尚未运行验证。
- 后续静态复查发现该登录夹具新用了 `httpx.Client` 但漏掉局部导入；已补 `import httpx`，AST 与 `git diff --check` 通过。完整包验收仍因 C 盘可用空间 0 字节未运行。
- C 盘 Temp 盘点后，将 10 个 `plm-current-app-stage-*` 暂存目录复制至 `D:\PLM-Test-Temp\c-temp-program-migration-20261026`，共 199,718 个文件/12,512,565,082 字节；逐目录文件数、总字节和三份清单 SHA-256 一致。完整载荷逐文件摘要未在此次迁移中重跑；C 源目录保留。
- 迁移完成后 C 盘可用空间读数为 0 字节。为避免系统盘进一步耗尽，暂停完整包验收。所有本轮 smoke 数据设在 D 盘，但 Windows 宿主进程仍需本机系统空间。其他 Temp 文件、客户资料和 `plm-plan-*` 测试数据库目录未触碰；详见 `docs/progress/2026-10-26-c-temp-program-migration.md`。

## 中间未通过/阻塞记录（历史状态；以最终复验为准）

- 包内运行的上游 P51-A05 Prototype Package 页面曾超时；经隔离验收驱动调整不再作为本次判据。
- 当时尚未定位出 PlanVersion 运行时缺陷；后续最终复验发现前端原生 fetch receiver 问题，已在下文记录并修复。该中间候选的 Edge/HTTPS/PG结果未验，不计 PASS 或 FAIL。
- 本 WBS 保持未完成。Pilot、Gate 3、正式发行仍为 `NOT_READY`。

## 环境异常及安全边界

- `pnpm build` 使用的预置 Node 崩溃；随后本机 Node 24 类型分析因 Windows 可提交虚拟内存仅约 0.9 GB 而 OOM。未修改 pagefile、未结束其他进程。
- 首次 stage 参数校验在创建目标前拒绝了非直接 Temp 子目录；随后在精确目标下成功。没有覆盖或删除历史 stage。
- 每次失败 smoke 后候选包和已验证 stage 保持原样；smoke runner 按自身 finally 停止并清理其拥有的服务/布局。用户 `.tmp/` 未改动。

## Changed / Files / Migration / API / Tests

- Changed：修复 PlanVersionReadClient 的 fetch 调用上下文；增加 receiver-free 单测；完善仅供一次性验收的包内 Edge/PG 合成来源夹具及浏览器诊断。
- Files：本记录、`docs/changes/DEC-20261026-P51-A17-packaged-fixture-context.md`、`apps/frontend/src/modules/plan/api/planVersionReadClient.ts`及spec、`validation/plt-pkg-01-a09-p51-a05-prototype-packaged/verify.py`、`validation/plt-pkg-01-a09-p51-a17-planversion-packaged/verify.py`/`run-edge-browser.mjs`、`validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py`、前置smoke工具改动、`STATUS.md`、`CHANGELOG.md`。
- Migration/API：无。
- Intermediate tests：早期候选复验有过Session/CSRF夹具、原生fetch receiver和路由等待问题，均已在最终复验前修复；这些中间失败被保留作追溯，不表示最终状态。
- Intermediate result：曾为`IN_PROGRESS_BLOCKED_LOW_C_DRIVE_SPACE`，现已由最终`PASS_SCOPE_LIMITED`替代。
- Intermediate next：曾要求恢复空间后复验，现已完成；当前下一项见文末 `OUTPUT-01-A01`。

## 最终复验（2026-10-26）

- C 盘可用空间后来恢复；本次只读观察到约 26.4 GiB 可用，未由本任务删除 C Temp 文件。后续构建、Stage、Edge profile、PG 与 smoke 数据均定向至 D 盘。
- A17 首轮包内复验确认详情读取失败不是脚本静态标题误判：`PlanVersionReadClient` 以 `this.fetcher(...)` 调用原生浏览器 `fetch`，导致非法 receiver 在发请求前失败。按 `DEC-20261026-P51-A17` 的 CR-P51-A17-READ-FETCHER 记录修复并增加 receiver-free 单测；前端 199 files / 2069 tests、typecheck/build 通过。
- 新候选由源码提交 `f66bc60bf320288413db17868d79223d25f69ec5` 派生：`artifacts/package-prep/windows11/current-app-p51-a17-read-fetcher-20261026/current-app-candidate-81e8e383bcf7/NOT-FOR-RELEASE-windows11-current-app.zip`；SHA-256 `092471f2e088b5658d663f2c6bd43ee488e1848ed2e61ab004cb1b8ba0ef8a19`，22,246 payload files，`release_eligible=false`、`legal_clearance=false`。清洁 Stage 为 `D:\PLMToolTemp\plm-current-app-stage-p51a17-fetch-fix-20261026`，独立解包 hash 检查通过。
- 最终包内 Windows 11 Edge/HTTPS/PG 完整验收：Section/Outline 合成批准来源经正式 Owner/Review 路径生成；PlanVersion Create 201、匹配固定 Detail GET 200、页面显示版本 UUID 与两条 WBS、Validate PASS、PM 原子 SubmitReview、合成 Reviewer 只读查看均通过。PG 核对 Version/Review/Round=`IN_REVIEW`、2 WBS/2 Requirement/1 Validation、Decision=0。完整 smoke 结果 `SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS`，健康/HTTPS=200、0 API/PG restart、候选未变、临时进程/文件清理通过。
- 两次中间脚本失败均按证据修复：Create View 自动跳转详情页（脚本已改为校验完整 UUID 路由与正文）；`/versions/new` 与详情前缀重叠（等待条件已限定 UUID）。它们不是产品失败，也未被计为通过。
- 不变边界：无 Migration/API 变更，真实来源/身份/License 信任未验；本候选不是 Pilot 或正式发行。C Temp 未删除/移动；已知的旧 A16 rehearsal/历史 D 盘调试目录未清理或覆盖。

- 最终 Result：`PASS_SCOPE_LIMITED`；完整最终包内合成验收通过，不解除正式 Pilot/Gate/Release 阻塞。
- Next：`OUTPUT-01-A01`，基于冻结 DM-05/API-03核查 OutputRequest/Artifact 的 Schema/Owner/固定来源/Trace/下载边界并形成首个可验收切片，不预设合同可直接实现。
