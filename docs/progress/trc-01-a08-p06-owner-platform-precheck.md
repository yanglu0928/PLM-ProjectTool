# TRC-01-A08-P06：Trace supersede 关系 Owner/正式装配前置

日期：2026-10-02；Phase 2；结论：**PRECONDITION_BLOCKED（仅正式装配与非经理关系 Owner），转独立 Trace 创建任务**。P02/P04/P05 的内部/显式可选验收保留，不外推为正式平台可用。

冻结 API-02 对 `TRACE_LINK_SUPERSEDE` 允许 ProjectManager、关系 Owner；当前 Project 策略只允许当前 ACTIVE PM，`trc_links.created_by` 仍仅审计事实，端点 Document Owner 不证明边的 Owner。DEC-20261002-616 的权限边界同样适用，不把创建者推断为关系 Owner，也不凭 P04 的端点解析扩大角色。`entrypoints/api.py` 只在显式提供 Router 时挂载，`production_login.py` 未注入；默认与 Windows 正式组合仍 404。`STATUS.md` 所列正式 License 公钥、目标账户密钥/可信时间和跨平台恢复材料未齐，合成 PG18/临时信任不能替代生产供给。

处理：不改冻结 API/Schema/角色，不挂正式路由，不为关系 Owner 猜测身份/迁移历史。后续真实关系 Owner 规则与撤权证明需另立 Trace Change Request，记录历史归属/兼容/迁移与回滚、跨项目/失效端点/并发验收；正式装配需目标账户信任材料和真实链验收。Server2025/Debian 按实际环境单独标注。本文仅静态核查合同、策略、ORM 与入口；无产品代码、迁移、配置或新业务测试，Gate 3/UAT/可用程序包未通过。

Next：`TRC-01-A09-P01` 核查冻结 `TRACE_LINK_CREATE` 三字段公开引用与内部创建事务边界，若可复用 P04 Resolver，先做受权同事务输入/幂等，再做可选 HTTP；正式平台仍按客观信任证据决定。
