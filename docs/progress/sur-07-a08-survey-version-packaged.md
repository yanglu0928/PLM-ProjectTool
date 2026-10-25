# SUR-07-A08：调研问题版本 Windows 11 非发行包验收

日期：2026-10-25；当前状态：`P01_FRONTEND_FETCH_FIX_PASS / P02_SYNTHETIC_PACKAGED_EDGE_PG_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `SUR-07-A08`；只验固定非发行包内的调研版本 UI 写链及拒绝路径。|
|输入|A05～A07 已推送；冻结 SurveyVersion POST、当前批准交接来源 GET、既有包内项目→交接批准→调研定义前序链。|
|模块/API/权限|验收脚本与发现问题所需的 Survey 前端 GET 调用；不变更后端 API、Schema、License 或正式信任。|
|标准|干净提交绑定、清洁解包哈希、Edge/HTTPS/隔离 PG 版本创建、固定行与 MANUAL、唯一 Audit/收据、原号重放及匿名/错项目/只读/合成失效拒绝，临时资源清理。|
|边界|仅合成账户/资料/License；真人访谈/客户确认、正式公钥/服务账户/安装/升级、Gate/Pilot/Release 不由本项推定。|

首个候选绑定提交 `d3435e7d447ca38be39a4c55dce6efecb9a85447`，SHA-256 `e79144b169941dc9992e5e1decf7a4141a09e577168408323513b8b555dfa260`，`release_eligible=false`、`legal_clearance=false`；22,197 件清洁解包逐件哈希通过。首次默认 C 盘临时布局在复制时空间不足，未进入业务断言；工具清理了不完整目标布局，C 盘本轮解包副本仍保留，删除操作受执行策略阻止，未绕过。改在 D 盘专用 ASCII 临时目录后，同 SHA 包运行至交接批准及调研定义创建均通过，但调研版本页面在来源 GET 发起前显示来源不可用，A08 未通过。定位到新增 `SurveyHandoverSourceClient` 把浏览器原生 `fetch` 作为对象方法调用，接收者不正确；合成 mock 未覆盖该浏览器边界。先记录偏差，再补调用及回归，需重建并完整复验新固定候选。原候选及失败事实保留；无生产数据或客户资料外发。

`P01` 修复只将原生 `fetch` 取出后调用，不改变请求地址、头或后端合同；新增无接收者浏览器型测试。定向11、前端全量2038、TypeScript/构建通过。验收脚本增加显式 D 盘 ASCII 临时根，仅作用于本次合成运行；原业务/发行目录不变。

`P02` 从已同步干净提交 `c1a44366f29deac66a488168e26deecc73ceb221` 重建后端 wheel/前端包，固定候选 SHA-256 `4f090636986c5c2173a5fde48eb161a94e5ee285ce73a8deb529c8682e048f46`，22,197 载荷件及3清单文件在 D 盘独立清洁解包、逐件哈希通过；`release_eligible=false`、`legal_clearance=false`。包内 Windows 11 Edge/HTTPS/Caddy/Python 3.13/隔离 PG18 依次完成固定项目资料/Evidence/能力、交接两问题 DRAFT→送审→合成客户 Reviewer 批准、调研定义创建，以及受权实施成员页面创建一个 Survey DRAFT 问题版本。浏览器请求使用当前固定交接行 ID 和显式 MANUAL 合成面对面访谈说明，PG 验证一个版本/一个问题/两类来源/目标部门、唯一 `SURVEY_VERSION_CREATED` 成功 Audit 和完成收据；同原号重放仍返回同一版本。匿名、错项目、客户只读、伪固定来源和合成 EXPIRED 许可写入均拒绝，版本数不变。验收进程退出0，固定候选未改变，临时 PG/Caddy/Python/Edge、Vault 和安装布局均清理；D 盘解包 stage 与旧失败候选保留供追溯。

仅本切片合成验证通过，不代表真人访谈/客户确认、调研版本送审批准、正式公钥/目标服务账户/CA、法律清单、离线安装升级、自然 License 到期/撤销、完整纵向链/UAT/Gate 3～7/Pilot 或三平台正式 Release 已通过。下一任务 `SUR-07-A09` 核查当前 DRAFT 调研版本的校验、送审及受权评审入口，然后按最短纵向链继续。
