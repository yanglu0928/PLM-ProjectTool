# HND-05-A03-P02：交接 DRAFT 版本校验面板

日期：2026-10-25；状态：`FRONTEND_CONTRACT_PASS / PACKAGED_BROWSER_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A03-P02`；只把 P01 校验客户端接到交接详情已选 DRAFT 版本。|
|输入基线|Gate 2 冻结 HND 读取与 `:validate` 命令；P01 安全客户端定向13/前端全量1987及构建已同步。无 API/Schema/权限改动。|
|前置|详情页已有授权版本及问题只读展示；Manager/ImplementationMember 可校验，客户角色不可写；送审/Reviewer 仍独立。|
|页面行为|仅当前项目有权人员在 DRAFT 上显式点击校验；展示 PASS/阻断码及人工理解提示。持久化原操作 Key 至浏览器会话，未知结果先核审计、勾选后同号重试；跨版本/项目/会话切换清空可见报告。|
|风险|校验报告按执行时当前来源计算，不保证之后来源不变；PASS 不是正式批准、客户确认或自动送审。浏览器本地只保留元数据/Key，不存文档正文或客户输入。|
|验收|定向面板状态/权限/未知结果原号/切换清屏；既有详情回归与前端全量/typecheck/build。真实 Edge/HTTPS/PG/非发行包本片不预填通过，独立 P03。|

编码前条件满足；按单一问题实施页面，不修改冻结 API/数据库。

实施：详情页仅在已选择的 DRAFT 版本加载校验面板，使用当前项目角色和 P01 私有
客户端；报告分别解释七类阻断，并显式说明 PASS 不是客户确认、送审或批准。原 Key
只随 actor/project/analysis/version 元数据存于 `sessionStorage`，未知结果须先核审计，
勾选后同号重试；版本切换通过 keyed panel 卸载旧视图，不展示旧报告或套用旧 Key。

验收：面板定向4项与既有详情3项通过；前端全量186文件1991项、typecheck/build
退出0。无 API/Schema/权限/License 变更和数据迁移；可回退前端资源，既有校验 Audit
不删除。真实 Edge/HTTPS/PG、固定包中运行和客户/Reviewer 人工决定尚未验。
为缩短纵向链，下一独立任务先接 `HND-05-A04-P01` 送审安全客户端；校验/送审页面
齐全后进行一次组合包内验收，不能将本次前端合同写为包内 PASS。
