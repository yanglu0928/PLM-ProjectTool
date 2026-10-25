# HND-05-A05-P04：交接详情固定版本深链

日期：2026-10-25；状态：`HND_05_A05_P04_FIXED_VERSION_DEEPLINK_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A05-P04`；仅让交接详情可按显式固定 VersionId 读取，不修改 Review 页面。|
|输入基线|Gate 2 HND 不可变 Version GET/Item LIST、P03 评审页面固定 ID 展示、现有 HandoverReadClient 严格项目/Analysis/Version 解析。|
|前置|交接详情已有 `getVersion` 与 `listItems` 安全客户端；目前仅在当前列表页手动点击才能选中，无法直接指向历史固定版本。|
|模块/实体/API/权限|仅前端 Handover 详情与测试；使用原 GET，不增 API/Schema。Session、Project、来源、License 均由原客户端/服务端重验。|
|验收|`fixedVersionId` canonical UUID 即使不在当前列表页也精确读取；错误形态不请求、错项目/Analysis/Version 不显示任何问题；路由切换清除旧选择；普通手动选版回归、前端全量/typecheck/build。|
|风险/回滚|不允许错误 ID 回落最新版本；深链只是固定版本定位，不证明客户批准。仅前端资产可回退，历史 Review/Audit 保留；实际 Edge/PG/包内另验。|

编码前置满足。评审页把固定 ID 写入链接为下一独立 Review 任务，不在本片跨模块顺手修改。

实现：交接详情在 `fixedVersionId` 为 canonical 非零 UUID 时直接调用原精确
`getVersion` 与 `listItems`，不从当前版本列表查找；收到的项目、Analysis、Version
或问题归属不一致时不显示卡片。错误形态仅提示核对、不发固定版本请求，
不会自动显示最新版本；同页 query 改变清除旧选中内容。普通手动选版复用同一
读取路径。定向6项、前端全量188文件2,012项、typecheck/生产构建退出0。
无 API/Schema/License/权限更改或数据迁移；下一片由 Review 页面把本轮固定 ID
写入链接，随后独立包内 Edge/HTTPS/PG 复验，Pilot/Gate/Release仍 NOT_READY。
