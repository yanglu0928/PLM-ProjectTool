# CR-EXEC-042：OUT-01-A01-P43 Output 生产组合与 Publisher 信任编码前检查

日期：2026-11-07  
状态：PASS_WITH_LIMITATION（源码检查完成；P44 Hosted 运行时验证待执行）

## 当前阶段与 WBS

Phase 2 Platform Core / Windows 11 Pilot 纵向业务链。WBS：OUT-01-A01-P43。

## 基线与编码前检查

- 问题：P41/P42 已验证 PlanVersion 固定来源投影和 Output事务持久化，但P42使用合成Owner/Operation Capability。需确认Windows生产Output Create组合、公开路由挂载条件及实际Plugin signer trust来源，避免把合成能力误报为生产功能。
- 输入：冻结Architecture、DB Schema V1、API Contract V1；CR-EXEC-040/041；当前分支的Windows Output/Create、Production Login、Plugin Operation capability和签名者resolver源码。
- 范围：只读源码和只读包内信任清单检查；不改产品、接口、数据库或发布配置，不生成/签署插件。
- 生产接线：`create_windows_output_request_create_router`真实组合Plan Owner、Requirement Owner、内置模板/策略、Plugin Operation capability Repository及OutputRequestService；Plan/Requirement仍由Owner在事务内精确授权读取。
- API挂载：`create_app`只在收到显式router时挂载Output Create；`create_production_login_app`与只读`create_production_platform_app`均不开放写路由。仅`create_production_platform_write_app`及其trace变体设置`include_secret_write=True`后组合Output Create；此项是受控写模式，不等于Pilot已开放。
- 信任事实：包内 `apps/backend/src/plm_assistant/modules/plugin/trust/developer_keys.json` 当前为有效版本格式且 `keys=[]`。真实Capability Repository只有在精确唯一Operation、启用Installation、兼容Runtime、通过SIGNED_PACKAGE_VALID验证，并能解析ACTIVE Ed25519 signer时才返回trusted=true。空签名者清单不能为任意Operation建立正式信任；Output Resolver对缺失/不可信Capability拒绝，Output Create无部分写入。
- 结论：P43按PASS_WITH_LIMITATION完成。源码表明P44可在不注入合成信任/不改正式装配的前提下，验证真实Plugin capability reader + 空包内trust manifest使Output Create fail-closed。不能在当前约束下生成可信的正式插件Operation或实际文件；不以合成私钥、公钥或测试Capability伪装正式来源。

## 下一项 WBS：OUT-01-A01-P44

在GitHub Hosted Windows Server 2025 D盘owned临时目录中，通过隔离PG18验证实际Plugin capability repository + 空正式signer manifest导致的Output capability拒绝及零写入；如果真实HTTP组合不能安全构造，则直接验证Owner/Resolver边界并记录限制。仅合成身份、项目和固定PlanVersion；不执行PluginService/子进程，不生成文件，不更改schema/API/信任清单。实施前建立CR-EXEC-043。

## 验收、安全和回滚

- 必须用当前包内实际空manifest与真实Capability读层，不接受fake trusted=true。
- 验证请求拒绝且OutputRequest/ContextSnapshot/Job/Outbox/Audit/幂等收据均零新增；插件执行数为0。
- 只在GitHub Hosted runner的D盘owned目录执行；无客户数据/外部API，日志只输出白名单布尔/计数。
- 本P43无程序变更，回滚仅需移除本记录与状态条目；不影响P41/P42证据和已冻结基线。
- 本次没有在本机或C盘运行项目代码；Temp清理由执行环境策略拒绝，未删除任何内容。
