# CAP-02-A05-P03-P02-A03：Windows 11 多条目浏览器与非发行包验收

日期：2026-10-24；状态：`PRECHECK_PASS / VALIDATION_IN_PROGRESS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P03-P02-A03`；仅验收已提交的多条目用户链及新非发行候选，不改冻结产品合同。|
|输入/前置|CR-CAP-007 的合法 DEPRECATED 读取已通过 Win11 隔离 PG/HTTP；A02 页面定向10、前端全量1953/typecheck/build；源提交 `dd81bc69`。|
|边界|复用合成 GLOBAL 文档/Evidence/Capability/Review 的隔离 PG/HTTPS/Edge；不发送客户数据、不安装正式服务、不接正式私钥。|
|包前置|固定父包 SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f` 已重算一致；原候选 ZIP 保留不覆盖。|
|验收|重建后端 wheel+前端 dist，新候选逐件 Hash/清洁解包；Edge 实际两条独立来源/Evidence 进入同一 DRAFT、DEPRECATED 回读、Review 批准和 PG/Audit/收据；拒绝/原号/资源清理。|
|风险|仅本机合成身份、License、TLS、证据资格；正式发行公钥/服务账户、真人确认、安装升级/UAT/Gate/三平台未通过。若浏览器脚本当前缺双来源种子，先记录差异再扩验收夹具。|

验收进行中，不预填 PASS。
