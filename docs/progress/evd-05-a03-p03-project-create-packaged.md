# EVD-05-A03-P03：项目 Evidence 创建 Windows 11 非发行包验收

日期：2026-10-25；状态：`SYNTHETIC_PACKAGED_EDGE_PG_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|当前 Phase/WBS|Phase 2 / `EVD-05-A03-P03`；只验收 P02 项目 Evidence 用户路径与资格，不改变产品合同。|
|输入基线|CR-EXEC-002、P01/P02 前端回归、固定父包 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。|
|前置|干净提交、重建后端 wheel/前端 dist、父包/pgvector 摘要复核；仅新非发行候选可证明新页面。|
|涉及模块/实体/API|PROJECT DocumentVersion、Evidence CANDIDATE/ELIGIBLE、Audit/幂等收据，既有 `/api/v1/projects/{project_id}/evidence` 与资格路由。|
|权限|一次性合成 ProjectManager/ImplementationMember/CustomerManager、License、TLS；创建与资格按既有角色分别重验，真实客户确认另行验收。|
|验收|候选全件 Hash/清洁解包；Edge 选同项目固定版本创建整文档候选、只读回读，HTTPS 当前有权人员资格核定，PG 固定引用/指纹/Audit/收据，匿名/错项目拒绝及资源清理。|
|风险|此项不提供页段精确定位，不宣称真人资格、正式信任/安装/UAT/Gate/Pilot 或 Server 2025/Debian 13；大 ZIP 只保存在本机忽略区。|

结果待实际运行填写，不预填 PASS。

首次包内运行：候选清洁解包 22,196 件，Workflow 与项目文档/交接前置通过；新 Edge 页面实际提交 PROJECT Evidence POST 201，列表、Viewer 与当前资格 GET 均为 200。验收脚本在勾选“已核对”时误用标题 `#evidence-decision-title` 的后代选择器，导致浏览器脚本 `Uncaught`，资格 POST 尚未发出。修正为资格表单复选框并显式等待；候选产品 SHA 保持 `9557db0ee09f9252bd2967ed34db8a9ef626c4c1d0255cbeee202a15679346cb` 不变，临时布局/进程已清理；首轮不记 P03 PASS。

第二轮同候选在 Edge 中再次完成候选创建/列表/Viewer/当前资格 GET；提交后页面进入“原操作结果未确认”安全态，网络观察中没有 `:set-eligibility` POST，整轮退出 1，临时资源清理。源码核查发现 `EvidenceEligibilityClient.current()` 特意把原生 `fetch` 提取为局部变量，防止 Edge 以类实例作 receiver；但 SessionClient 的 PROJECT/GLOBAL 资格 POST 与原号回查仍以 `this.fetcher(...)` 调用，原生浏览器会因 receiver 错误在发请求前抛错，随后被映射为不确定结果。这是已存在的运行链缺陷，不是证据资格本身失败。先增加 receiver-sensitive 回归，统一修正四个 Evidence 资格传输方法；无 API/Schema/权限变化，旧候选保留。随后从新干净提交重建非发行包再跑完整链，不以客户端合成 mock PASS 取代实际 Edge。

传输修复：四处 Evidence 资格写/原号回查改为局部 `fetcher` 调用，原 CSRF/ETag/Key/超时/错误行为不变。新增 receiver-sensitive 定向，Evidence/Session 两文件合计180项、前端全量1962项与 typecheck/build退出0。此为源码合同与构建通过，不是新包或人工资格验收；新包待重建。首、次轮的候选 SHA 和失败证据保留。

修复后第三轮：从已同步的干净提交 `1906465da8445311faa3554ed06862893db7d139` 重建新非发行候选，ZIP SHA-256 `7d389ebf28df2f6bcc7c35842def653d691b5b8918654785fd7569a07eb9768b`，本机忽略区路径 `artifacts/package-prep/windows11/current-app-evd-a03-p03-r2-20261025/current-app-candidate-3f61fcbb4917/NOT-FOR-RELEASE-windows11-current-app.zip`。后端 wheel SHA `ecbed9b6118c01a6617a1bc68ebfb1fa50ef5dc984951eaf0f162d8817e4e6ef` 未变，仅换入修复后的前端资产。候选构建与清洁解包校验通过，payload 22,196 件；运行中没有将本机旧候选改写为通过。

完整包内验收退出0：Windows 11 上以一次性合成 License/公钥、隔离 PostgreSQL 18、打包 Caddy/FastAPI/Edge 完成 Workflow 和固定项目文档/交接分析前置；Edge 中项目 Evidence 创建 `CANDIDATE`、原文 Viewer 读取及合成授权资格写为 `ELIGIBLE`。PG 核实固定文档/版本、资格、Audit，以及 `V1_EVIDENCE_CREATE` 和 `V1_EVIDENCE_SET_ELIGIBILITY` 各一条幂等回执；匿名、未分配项目用户、跨项目文档来源均拒绝，未增加非法 Evidence。部署布局/进程/隔离库均按验收脚本清理。此结果仅证明 Windows 11 合成信任下的该切片；资格不是客户真人确认，整文档定位不等于页段精确定位，正式发行公钥与目标服务账户、法律放行、离线安装/升级、完整纵向业务链、UAT/Gate 3～7、Server 2025/Debian 13 仍待，Pilot/Release 均 `NOT_READY`。Next：重新执行 `HND-05-A02` 编码前检查，接入有来源的问题卡片版本创建入口。
