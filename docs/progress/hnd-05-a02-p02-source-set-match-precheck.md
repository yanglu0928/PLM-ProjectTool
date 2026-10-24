# HND-05-A02-P02：交接首版本固定来源匹配前置

日期：2026-10-25；状态：`FRONTEND_SOURCE_MATCH_CONTRACT_PASS / UI_PENDING`。

|检查项|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A02-P02`；只解决首个版本无法从分析详情回读固定文档列表时的安全匹配，不生成问题或写入版本。|
|输入基线|冻结 Handover `source_set_ref` 算法：`handover-source-set.v1\n` + 按 UUID 字符串排序的 DocumentVersionId、换行连接，再 UTF-8/SHA-256；P01 客户端与现有项目 Document 元数据读路径。|
|前置|Analysis 只持久化来源哈希；首次 Version 没有 `source_documents` 可回读。用户重选同项目、ACTIVE 且 AVAILABLE 的固定文档版本，客户端仅做本地相等提示，服务端 `HandoverSourceValidator` 仍作权威归属/状态/集合重验。|
|API/Schema/权限|无改动，不反推或枚举哈希，不缓存文档正文；只处理 1～500 个非零规范 UUID。|
|验收|与后端规范相同的单/多文档测试向量、顺序无关、错/空/重复/不规范来源拒绝；全量前端回归和构建。浏览器页面与真实 PG 留后续 WBS。|
|风险/回滚|重新选择仍增加用户操作，但不会产生未经验证的来源；若需要未来直接回读首版来源，必须另走可追溯 CR/迁移/兼容/回滚。撤掉本地匹配器不影响现有分析/版本数据。|

编码前结论：满足独立纯客户端匹配器前置。其 PASS 不表示来源文档自动找回，也不表示 Handover Version 创建或 Gate/Pilot 通过。

实施结果：新增纯客户端规范化/`crypto.subtle` SHA-256 匹配器，只处理 DocumentId/固定 DocumentVersionId 元数据。后端 `canonical_handover_source_set_ref` 生成的双版本向量为 `sha256:5d079216a7c79d5da45ce91d9a80a60cd319b5da9a01a646038065cfa5d65c26`；定向3项覆盖规范化载荷、顺序无关、缺/错/重复来源及不可用摘要拒绝。首次测试采用 Node 加密实现时，前端 tsconfig 不含 Node 类型，typecheck 失败；改为注入摘要边界、核对规范化载荷及固定后端向量后，定向3、前端全量1969/typecheck/build退出0。实际浏览器 WebCrypto、页面来源选择与 Handover Version 写入未验。Next：`HND-05-A02-P03` 卡片式版本创建页面，提交前重新读取授权分析/来源/能力/证据并用此指纹匹配器预筛，后端仍为权威；无来源不能生成假问题。
