# CAP-02-A05-P03-P02-A03：Windows 11 多条目浏览器与非发行包验收

日期：2026-10-24～2026-10-25；状态：`WINDOWS_11_SYNTHETIC_PACKAGED_EDGE_PG_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P03-P02-A03`；仅验收已提交的多条目用户链及新非发行候选，不改冻结产品合同。|
|输入/前置|CR-CAP-007 的合法 DEPRECATED 读取已通过 Win11 隔离 PG/HTTP；A02 页面定向10、前端全量1953/typecheck/build；源提交 `dd81bc69`。|
|边界|复用合成 GLOBAL 文档/Evidence/Capability/Review 的隔离 PG/HTTPS/Edge；不发送客户数据、不安装正式服务、不接正式私钥。|
|包前置|固定父包 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f` 已重算一致；原候选 ZIP 保留不覆盖。|
|验收|重建后端 wheel+前端 dist，新候选逐件 Hash/清洁解包；Edge 实际两条独立来源/Evidence 进入同一 DRAFT、DEPRECATED 回读、Review 批准和 PG/Audit/收据；拒绝/原号/资源清理。|
|风险|仅本机合成身份、License、TLS、证据资格；正式发行公钥/服务账户、真人确认、安装升级/UAT/Gate/三平台未通过。若浏览器脚本当前缺双来源种子，先记录差异再扩验收夹具。|

以下保留四轮原始验收过程；仅第四轮完整退出 0 后记该片合成验收 PASS。

首次包内验收：新候选已清洁解包 22,196 件且摘要不变；既有 Workflow、GLOBAL 文档上传→基线身份、整文档 Evidence CANDIDATE 的包内 HTTPS/Edge/PG 前置通过。新增第二来源的测试夹具调用旧 Schema 种子函数，因临时运行账户没有设置 `session_replication_role` 的权限而失败；尚未执行多条目页面，不记产品缺陷或本 WBS PASS。调整为通过产品自身的 GLOBAL 上传意图→内容→提交和 Evidence 创建→合成资格 HTTP 路径生成第二来源，保留同一候选 SHA，复验脚本。无需修改正式 Schema/API/权限；风险为额外合成业务数据只存在可弃临时库，失败/回滚均由包内运行夹具清理，不触碰客户数据。

第二轮同包前置和第二来源真实 HTTP 创建/资格通过；Edge 脚本在点击文档后仅等待静态“可用版本”标题，没有等待异步版本按钮，因而报缺“选用此固定版本”。页面尚未发版本 POST，不记多条目 PASS 或产品缺陷。调整为等待实际版本按钮与证据选项、导航时容忍 CDP 上下文短暂替换，并使用条目列表 DOM 数量判断阶段；候选和产品字节不变，第三轮复验待执行。

第三轮同包 Edge 页面完成两份独立来源/证据的两条目 DRAFT（含 DEPRECATED），PG 项/固定引用/Audit、管理员回读、VALIDATE、两个 Reviewer 固定内容读取与决定均已到达预期；末尾比较 HTTP `current_approved_version_ref` 字符串与 PG `version_id` UUID 对象时，夹具类型未统一，断言失败。已改为比较规范字符串；这不是产品指针不一致的证据，亦不能凭未完成断言宣称整轮 PASS。产品候选 SHA 不变，第四轮复验待执行。

第四轮完整复验退出 0：同一清洁解包候选中，实际包内 PG18、Python、Caddy/HTTPS 与 Edge 经过两份独立 GLOBAL 固定 Document/Evidence，页面提交含两条来源、其中一条 DEPRECATED 的单个 DRAFT；HTTP 回读、PG 固定来源/状态、VALIDATE、两名合成 Reviewer 固定内容核对和批准、当前批准指针、Audit/收据全部通过。此前三次失败均为验收夹具问题，按顺序修正并保留记录，未更改产品候选字节。

新候选来源提交 `28e619e3`（含 A02 产品提交 `dd81bc69`）；后端 wheel SHA-256 `09e6990e68076aa032e473e5de201d658919442704fb1b22669cab7d46917428`；本机忽略区非发行 ZIP `artifacts/package-prep/windows11/current-app-candidate-bfcb9f382811/NOT-FOR-RELEASE-windows11-current-app.zip` 为 654,895,827 字节，SHA-256 `d944d77d74e42c31b16e65c87972f496434e93f14f7c2c6afa9ef5976b400925`。22,196 件载荷逐件 Hash 清洁解包通过；第四轮后原 ZIP 摘要不变，临时布局/进程/合成 Vault 已清理。可复验入口：`validation/cap-02-a05-p03-p02-a03-packaged-multi-item/verify.py`。

边界：所有账户、License、公钥、TLS、Document、Evidence 与评审均为合成；不代表真人客户确认或正式信任。包不可发行，Pilot 仍 NOT_READY；未验正式离线安装/升级、Windows Server 2025、Debian 13、UAT 或 Gate。独立待办：P05-P04 License 自然到期/撤销负例，HND 后续纵向业务链与正式安装信任前置。
