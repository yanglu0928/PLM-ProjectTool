# EVD-01-A04-P03-A08-P08：资格回查当前身份边界

日期：2026-10-01；Phase 2 Platform Core；结果：`ACCESS_UNIT_PASS / RESOURCE_PROOF_OPEN`。

编码前检查：输入 CR-EVD-004、现有资格写入 Session/CSRF/Project 角色边界；P07 收据只读方法已通过。仅 Evidence Application Access 与单测，不改 Schema、公开 API、角色基线或依赖。此项只验证操作者的**当前** Session/CSRF 与 PM/CustomerManager、GLOBAL Admin，不验证指定 Evidence 行，后者仍是下一 Service 前置。

现有 `require_in_transaction` 增加明确白名单 `V1_EVIDENCE_ELIGIBILITY_OPERATION_LOOKUP`，继续锁定真实 Auth/Project 事实；不接受任意 operation。项目 ACTIVE/ARCHIVED 下当前 PM/CustomerManager 可回查历史，ARCHIVED 下原 `SET_ELIGIBILITY` 仍返回 `PROJECT_ARCHIVED`，未知项目状态、停用/移除成员、非决策角色或 Session/CSRF 不匹配失败关闭。GLOBAL 仍只接受当前 DeploymentAdmin，不作为项目旁路。原写入路径不变。

新增2项定向权限单测；定向共5项 PASS，Windows11/Python3.13 后端全量1,803项 PASS、3项既有环境跳过。未运行真实 PostgreSQL 授权并发、具体 Evidence Scope/存在性、收据关联或 HTTP；不能将本 Access Port 单独开放。无 Migration/公开 API；回滚撤去新 operation 白名单，不影响原写入或历史收据。Gate3/可用包仍开放。
