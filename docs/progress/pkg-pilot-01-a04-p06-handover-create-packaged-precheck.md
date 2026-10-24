# PKG-PILOT-01-A04-P06：新候选交接分析创建包内验收

日期：2026-10-24；状态：`SYNTHETIC_EDGE_PG_PASS / PILOT_NOT_READY`。

|检查项|结论|
|---|---|
|Phase / WBS|Phase 2 / `PKG-PILOT-01-A04-P06`；从 `HND-05-A01` 已验源码重建非发行候选，验证项目文档固定版本选择→交接分析创建|
|输入基线|CR-EXEC-002、已冻结 `/api/v1`；源码提交 `5ce82bff`，P45 固定父包 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、Python pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`|
|前置|HND-05-A01 定向16、前端全量1879/typecheck/build PASS，提交已同步 origin；既有非发行候选包内 PG/API/Caddy/合成License/Edge项目创建 PASS。父包及 wheel 重算 SHA 后才重新组包。|
|模块/实体/API|仅受控非发行打包与验收夹具；Document/DocumentVersion、HandoverAnalysis、Audit/Receipt；使用既有上传/文档元数据/冻结 Handover POST，不改产品 Schema/API。|
|权限/安全|一次性合成 ProjectManager、隔离 PG/测试 License/自签 HTTPS；不外发客户资料、不保存私钥、不将合成信任写入候选；不把真实文档或客户确认当作夹具。|
|验收|包体清单/逐件哈希、清洁暂存、同 SHA；Edge 选择固定版本并创建交接分析、回读详情；PG 验证来源集合/单 Analysis/Audit/幂等收据，异常/跨项目/无来源拒绝；临时 Vault、进程、安装布局清理。|
|风险|本次新增 UI 不在旧候选；来源必须由文档安全上传产生并处于 AVAILABLE，不能伪造；现有包内浏览器夹具可能不包含写流程。若完整证明无法完成，分别记录完成片与客观阻塞，不虚报 Pilot。|

本项未获得正式发行公钥/服务账户/CA/法律放行；只允许一次性合成非发行验收。新候选不可称安装包或交付包，正式 Gate/Pilot 维持 `NOT_READY`。

## 首轮运行记录

源提交 `c52f6976adebcd48cb70a9437b2bee63896df27b` 的非发行候选 SHA `5b2ab7c225f024126ce32436ec29bf378ed5c0296173377dc2dd050fd83458e6`（654,847,549 字节、22,191 载荷）已构建并独立清洁解包通过；两个测试布局中包内 Workflow HTTPS/License/幂等/CSRF/冲突/Audit 前置通过。首轮真实 Edge 登录和项目列表 200 后，验收脚本只等待项目详情标题、未等待异步项目详情链接加载即点击文档入口，报 `missing UI action` 并退出1；未触发文档上传/交接 POST，不能把后续业务记为通过，也不能据此判产品缺入口。隔离服务/布局由烟测清理。补充实际链接就绪等待后将使用同一候选复验，保留本失败记录。

## 同候选复验结果

补足详情异步链接等待后，以同一 SHA 再次启动两份隔离布局；包内 PG18/API/Caddy、合成有效 License、HTTPS 登录及 Workflow GET/START/回放/CSRF/冲突/Audit 前置通过。真实 Edge 从合成项目进入文档页，在浏览器内存生成纯测试 `.txt`，完成上传意图→内容→提交，回到列表读取 `ACTIVE` 文档，再进入交接创建页选择其 `AVAILABLE` 固定版本，提交分析并打开详情。浏览器观察 14 个 API 响应，无非 2xx、加载失败或运行异常，固定标记 `PKG_PILOT_01_A04_P06_HANDOVER_EDGE_PASS`。

隔离 PG 复查该项目恰一份匹配标题的文档及可用最新版本、恰一条由合成负责人创建的 `ACTIVE` HandoverAnalysis、来源集合哈希格式、单条 `HND_ANALYSIS_CREATED` Audit 与单条完成的 `V1_HND_ANALYSIS_CREATE` 持久幂等收据。随包验收器退出0；候选 SHA 前后不变，48 个合成 Vault 目标无残留、临时文件/PG/API/Caddy/Edge 进程清理通过。清洁暂存目录保留为后续只读验收输入；不上传 655MB 候选 ZIP 至 GitHub。

本项仅关闭“合成正向文档→交接创建”的包内切片；前置表中无来源、跨项目等 Handover 创建负例矩阵未在本轮包内 HTTP 实测，需独立完成并记录后才能把 `PKG-PILOT-01-A04-P06` 整体标 PASS。后续分析版本/问题/调研→需求→原型→方案→计划输出、真实公钥/服务账户/CA、法律、离线安装升级、UAT/Gate/正式三平台结论均未由本轮通过。Result：`SYNTHETIC_POSITIVE_EDGE_PG_PASS / P06_OPEN`；Next：包内负例矩阵与下一纵向链切片。

## 负例首轮夹具失败

在同一固定候选下，正向 Workflow/Edge 流程再次完成，但跨项目负例夹具试图让已有负责人同时成为第二项目的活跃成员，被 `uq_prj_members__user_active` 拒绝；拒绝发生于准备测试账户/项目阶段，三个 Handover 负例尚不能报 PASS。保留本次退出1结果，不将夹具约束误报为产品创建缺陷。复验夹具改为第二个合成账户管理第二项目，使用独立登录/CSRF 测跨项目固定版本；产品 Schema 与权限规则不改。

修订后的下一轮在正向 Workflow/Edge 后到达首个包内负例：空来源被 HTTP 422 拒绝，服务返回冻结创建校验的 `VALIDATION_FAILED`，而验收脚本误期望 `HANDOVER_SOURCE_REQUIRED`，故该轮退出1；服务行为与既有验证合同一致，并未接受空来源。跨项目及无权限两个断言尚未执行，不报告通过。改脚本预期为实际合同后继续同候选复验，前两轮失败记录均保留。

## 最终独立复验

同一候选 SHA 再次完成包内 Workflow HTTPS 前置、真实 Edge 合成文档上传→固定版本→交接分析创建（14个API响应，无浏览器运行/网络异常）和 PG 单文档版本/单分析/Audit/幂等收据检查。另以原合成负责人验证空来源 HTTP 422 `VALIDATION_FAILED`；因数据库限制单用户同时仅有一个活跃项目成员，使用第二合成用户、第二受控项目及独立登录/CSRF，验证引用首项目固定版本的跨项目创建 HTTP 422 `HANDOVER_SOURCE_REQUIRED`，对未分配的首项目创建 HTTP 404 `RESOURCE_NOT_FOUND`。拒绝后两项目合计仍恰一条正向分析及一条创建 Audit，无额外业务事实。验收器退出0，`fixed_candidate_unmodified=true`，候选 SHA 不变；48 个临时 Vault 目标无残留，临时布局/PG/API/Caddy/Edge 进程清理通过。历史三轮脚本/夹具失败均保留在上文，不合并或伪装为首轮通过。

Result：`PKG-PILOT-01-A04-P06_SYNTHETIC_EDGE_PG_PASS`，仅 Win11 一次性合成信任下的交接创建切片。Next：`HND-05-A02` 核查并实现分析版本/问题卡片的用户创建入口，继续纵向链；正式信任/法律、离线安装升级、真实客户确认、UAT/Gate 3～7、Windows Server 2025/Debian 13 正式发行均未通过，Pilot/Release 仍 `NOT_READY`。
