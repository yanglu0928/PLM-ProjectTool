# CAP-02-A03-P02 / A04-P02：全局能力来源与基线身份包内验收

日期：2026-10-24；状态：`SYNTHETIC_POSITIVE_EDGE_PG_PASS / PILOT_NOT_READY`。

|检查项|结论|
|---|---|
|Phase / WBS|Phase 2 / `CAP-02-A03-P02` 上传与 `CAP-02-A04-P02` 基线身份创建分别验收；不在本项创建能力条目或批准版本。|
|输入基线|`CR-EXEC-002`、冻结 `/api/v1`；前端源码定向/全量 1904 项、typecheck/build PASS；源提交 `b1f3839ca0ef98c5adcb8e0d832ab4019718ffca`。|
|前置|Windows 显式组合已包含 GLOBAL Document 与 Capability API；父候选 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。|
|模块/实体/API|不改产品代码、DB Schema 或 API；只新增独立验收夹具。验证上传意图/内容/提交、固定文档版本读、Baseline POST/GET、Audit 与来源集合。|
|权限/安全|一次性隔离 PostgreSQL、Caddy HTTPS、Edge、合成 DeploymentAdmin 与测试 License；不读取或外发客户资料，不写入正式公钥或 License 私钥。|
|验收|固定包逐件哈希与清洁解包；真实 Edge 上传内存合成文本→独立观察 GLOBAL `AVAILABLE` 固定版本→创建基线身份→回读详情；PG 单文档/版本、来源哈希、单基线及审计；临时 Vault/进程/布局清理。|
|风险|仅正向合成链，不等同权限负例全矩阵、正式批准版本或客户确认；正式信任、法律放行、离线安装升级、Gate/Pilot/Release 仍未通过。|

## 候选与首轮证据

从固定父包、当前源构建 wheel 与前端 dist 组成非发行候选，SHA `bbace47d347919ae625372e35d1d5764c4004b97cf5038458a01ac15b1d51876`，654,859,305 字节、22,191 个载荷文件；`release_eligible=false`、`legal_clearance=false`。独立清洁解包通过，候选 ZIP 保持本机忽略路径，不上传 GitHub，也不称安装包。

首轮包内 Workflow HTTPS/License/CSRF/重放/Audit 前置通过；Edge 完成 GLOBAL 上传与 Baseline 页面创建，随后验收夹具在 SQL 复查中误写 `d.category`，数据库真实列为 `d.document_category`，故整轮退出 1。该失败只涉及验收夹具，不能视作完整端到端 PASS；已修正并在同一候选 SHA 下复验。产品 Schema/API 未改，首轮失败记录保留。

## 同候选完整复验

修正夹具后在同一候选 SHA 下重新清洁复制两份 22,194 件布局。包内 PG18/API/Caddy、合成有效 License、HTTPS 登录/Session、无 License 拒绝 403、Workflow GET/START/重放/CSRF/冲突/Audit 前置通过。真实 Edge 从管理员登录进入 GLOBAL 来源页，在浏览器内存创建纯合成 `.txt`，完成上传意图→内容→提交；另发 GLOBAL 文档与固定版本读取，确认 `ACTIVE`/`AVAILABLE`，再由来源选择页创建身份并反读详情。浏览器观察 13 个相关 API 响应，无非 2xx、加载失败或运行异常，标记 `CAP_02_A03_A04_P02_PACKAGED_EDGE_PASS`。

隔离 PG 复核恰一份 `GLOBAL/STANDARD_CAPABILITY` 合成文档及其 `AVAILABLE` 固定版本、恰一条 `ACTIVE` 基线身份，来源集合哈希与所选 DocumentVersionId 精确匹配；`DOCUMENT_UPLOAD_CREATE`、`DOCUMENT_UPLOAD_CONTENT_STAGED`、`DOCUMENT_UPLOAD_COMMIT`、`CAP_BASELINE_CREATED` 各恰一条合成管理员 Audit。包内验收器退出 0；候选 SHA 前后不变，48 个合成 Vault 目标、PG/API/Caddy/Edge 进程与临时布局清理通过。清洁暂存目录仅作本机后续只读输入。

结果仅关闭 Win11 一次性合成信任的正向 GLOBAL 文档→基线身份链。基线当前批准版本仍为空，不能作为正式能力依据或供交接分析版本引用；CapabilityVersion/Item/Evidence/Review 用户路径、包内普通用户/匿名/失效 License 等负例矩阵、真实信任/法律/离线安装升级、完整纵向 UAT、Gate 3～7 和正式三平台发行仍未通过。下一项先补 CapabilityVersion/Item/Evidence/Review 的用户操作路径；负例矩阵保留独立验收任务，不被正向 PASS 取代。
