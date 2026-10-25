# HND-05-A05-P06：交接 Review 读取与决定 Windows 11 非发行包验收

日期：2026-10-25；状态：`SYNTHETIC_PACKAGED_EDGE_PG_PASS / PILOT_NOT_READY`。

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

## 执行中证据与夹具偏差

- 由干净源提交 `98df564eab7e0fbc449bdb37c98eb315e052a6e9` 重建 Python 3.13 后端 wheel
  （SHA-256 `b2053a4a4b3e1648293514cbfd59f73786b227e3a2abf64ce4d11a7e99d10d4e`），
  同原固定 parent 合成非发行候选 ZIP（SHA-256
  `4cd0b60aaa439fd9e0a349233b065fa79bc6caacceaca017ec80791957fe3dc7`）；
  `release_eligible=false`、`legal_clearance=false`。独立解包 22,196 件载荷、3 件清单，
  逐件哈希 `CLEAN_EXTRACT_HASH_PASS`。ZIP 留本机 ignored artifacts，不上传远端。
- 第一轮包内前序链至 Handover `IN_REVIEW` 均通过；本轮夹具把实际表
  `rvw_review_decisions` 误写为 `rvw_decisions`，在决定前失败。修正夹具，无产品改动。
- 第二轮同样通过前序链；本轮 Review GET 使用前序项目测试刻意留在共享客户端上的
  外项目登录身份，返回 404 为正确隔离。夹具改为显式新建当前项目经理会话，并将旧
  外项目会话作为 404 负例；仍未据此判 P06 通过。
- 第三轮前序链通过，但经理合成账号已达到生产登录限流，新增登录 429；未绕过限流。
  夹具改为一次性合成当前项目非评审成员，单次登录验证可读/不可决定；外项目 404
  和客户评审人页面决定仍保留。该测试身份不进入产品或正式业务事实。

## 独立验收结论

第四轮固定 SHA 非发行候选完整复验退出码 0，`HND_05_A05_P06_PACKAGED_EDGE_PASS`
及 `HND_05_A05_P06_PACKAGED_PG_PASS`。安装前逐件哈希、实际临时布局、
Windows 11 Edge/HTTPS/Caddy/Python 3.13/PostgreSQL 18 的前序项目、固定文档、
Evidence、能力及交接 DRAFT→校验→IN_REVIEW 链均通过。受分配的合成客户确认人
经 Review GET 打开本轮固定交接版本，确认两张问题卡片后从页面批准；同一操作号
重放返回原结果。PG 验证 Review/交接版本与当前批准指针为 APPROVED，唯一决定、
唯一 `V1_REVIEW_DECIDE` 完成收据、唯一 `HND_VERSION_APPROVED` Audit。

匿名读取 401、外项目读取 404、当前项目非评审人决定 404、错误项目 404、
合成 EXPIRED 投影后读取 403，且拒绝未增决定。临时 PostgreSQL、服务进程、
安装布局和合成 Vault 由演练脚本清理；本机独立解包目录与 ignored ZIP 保留作
可复核样本，不进入 Git。第四轮成功不删除前三轮夹具失败记录。

范围仅是 Windows 11 合成信任下交接 Review 这一纵向切片。真实客户确认、
License 自然到期/撤销、正式发行公钥与服务账户/CA/法律放行、离线安装升级、
调研→需求→原型→方案→实施 WBS→输出文件、UAT/Gate 3～7、Windows Server 2025/
Debian 13 均未由本轮证明。下一 WBS 进入 `PKG-PILOT-01-A04-P07` 的调研入口
前置核查，从已批准交接版本到实际调研创建的最短链继续推进。
