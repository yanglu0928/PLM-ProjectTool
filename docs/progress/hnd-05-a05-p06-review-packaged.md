# HND-05-A05-P06：交接 Review 读取与决定 Windows 11 非发行包验收

日期：2026-10-25；状态：`PRECHECK_PASS / NEW_PACKAGED_EDGE_PG_PENDING`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A05-P06`；仅验证已实现的交接送审后 Review GET、固定版本深链与客户评审决定，不改冻结 API/Schema。|
|输入基线|已同步干净提交 `d1f7bf30`；P01 后端 HND-02 GET 隔离 PG/HTTP、P02～P05 前端定向/全量与构建通过；HND-05-A04-P03 旧非发行包只含送审前链，不能证明新功能。|
|前置|固定 parent 非发行候选 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；PostgreSQL/pgvector 既有本地 wheel、当前 Vue dist 可重建；须重建本轮后端 wheel 且候选绑定干净提交。|
|模块/实体/API/权限|验收夹具和候选包；Review/HND/PG 只使用已冻结端点。客户决定由受权合成成员经真实浏览器/HTTPS/服务端写入；不伪造数据库批准。|
|验收|独立清洁解包逐件哈希；包内合成 Edge/HTTPS/PG 送审→HND Review GET→精确固定版本导航→决定→状态/Audit/收据，原号重放及匿名、跨项目、非评审人、失效 License 拒绝；测试进程/Vault/库/布局清理。|
|风险/回滚|合成身份/License/TLS 只供内部测试；`release_eligible=false`、`legal_clearance=false`，不上传大 ZIP/Secret/客户资料，不代表正式信任/真人确认/Pilot/Gate/Release。打包失败保留证据，前置不满足停止该任务。|

前置核查通过，可准备固定非发行候选。P01 先前 wheel 构建尝试因环境缺 pip/setuptools
未成功，本轮会使用 Python 3.13 受控构建环境；只有新 wheel/候选字节与源码绑定后才能
开展包内业务验收。正式 Windows 安装仍缺发行公钥/操作员仪式，不以合成测试补齐。
