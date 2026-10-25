# CAP-02-A05-P04-P03-A04-P02-P05-P04：固定候选包 License 自然失效

日期：2026-10-25；结果：`WINDOWS_11_SYNTHETIC_PACKAGED_LICENSE_NATURAL_EXPIRY_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A04-P02-P05-P04`；在同一固定 Windows 11 非发行候选包验证签名 License 自然越期后的 Review 拒绝行为。|
|输入基线|`CR-CAP-006`、`CAP-02-A05-P04-P03-A04-P02-P05-P02/P03`；候选 SHA-256 `f2a2385538b111a1a36e3761086e0f4e5749554a3c57bde8941c0fb11080e095`。|
|前置任务|同包 P05-P02 正向 Review 链及 P05-P03 身份/游标/重放负例已通过；包和只读暂存经本轮全量重验。|
|涉及模块/实体/API|仅改包内验收脚本与通用合成 HTTPS smoke helper；验证 Review、Round、Decision、Capability baseline 指针及 License Runtime Audit。无产品代码、ORM、Migration 或 API Contract 变更。|
|权限与验收|签名 License 在 `valid_to` 前允许受分配 Reviewer 读取 Review/固定版本/条目；自然越期后上述固定内容读取及决定 POST 均返回 403 `LICENSE_OPERATION_DENIED`；Review 保持 `IN_REVIEW`、Round 仍为活动轮次、Decision 数为 0、批准指针为空，并存在 `LICENSE_RUNTIME_CHECK/DENIED/EXPIRED` 审计。不得改系统时钟。|
|风险|仅合成许可证、合成身份和 Windows 11 临时 PostgreSQL；不证明正式信任、发行适格、真人决定或其他平台兼容。|

## 执行与结果

在候选 SHA 不变的同一包上完成 22,199 件 payload 的清洁解包/哈希检查、Windows 临时安装布局、包内 PG18/API/Caddy/HTTPS/Edge 前置正向链。合成 Ed25519 License 在应用和 HTTPS 服务就绪后才签发，等待其载荷的真实 `valid_to` 越过，不调整系统时间。随后固定版本 GET、条目 GET、Review 决定 POST 均得到预期 403；PostgreSQL 核对 Review=`IN_REVIEW`、活动轮次仍指向原 round、决策数 0、批准指针 `NULL`，且 License 到期拒绝审计存在、没有 Review 决定 Audit。脚本输出 `CAP_02_P05_P04_LICENSE_NATURAL_EXPIRY_PASS`，退出 0。

四次未通过尝试均为验收夹具缺陷而非产品失败，已修复并保留在同一脚本历史：第一轮签名过早导致有效期在安装准备时耗尽；第二轮回调未从上下文读取签名文档；第三轮数据库字段名错误；第四轮状态值比较未规范化 UUID 字符串。第五轮完整通过。候选前后 SHA 一致；临时 PostgreSQL/API/Caddy/进程、安装目录和 48 个合成 Vault key 均清理，`release_eligible=false`、`legal_clearance=false`。

## 交付信息

- Changed：License 计时延后到 HTTPS/应用就绪；补充自然失效正负请求、数据库状态/决策/Audit/批准指针断言；新增 P05-P04 入口脚本。
- Files：`tools/smoke_packaged_platform_write_https.py`、`validation/cap-02-a05-p04-p03-a04-p02-p05-p02-packaged-review/verify.py`、`validation/cap-02-a05-p04-p03-a04-p02-p05-p04-license-expiry/verify.py`、本记录、`CR-CAP-006`、`STATUS.md`、`CHANGELOG.md`。
- Migration/API：无。
- Tests：三个脚本 `py_compile` 通过；固定候选包 SHA/清洁安装和实际 Windows 11 Edge/HTTPS/PostgreSQL 18 端到端验收通过；候选、进程、临时文件及 Vault 清理通过。
- Known issues：正式信任锚、服务账户 Vault/ACL/CA、真人评审、正式安装/升级、Windows Server 2025、Debian 13、Gate 3/Pilot/Release 仍未通过。
- Next：`SUR-07-A12-P01` 编码前核查最新 Survey A10/A11 与现有包内验收链差异，计划从当前干净提交重建候选并验证 DRAFT Validate→原子送审回执；不得将合成 Reviewer 结果称为真人客户确认。本项不改变 Gate/Pilot 结论。
