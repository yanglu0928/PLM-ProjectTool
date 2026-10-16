# AI-03-A07-P01：Prompt 只读元数据前置核查

日期：2026-10-02；依据冻结 API-03 `AI_PROMPT_LIST/GET`、DM-04、现有 Schema0059～0062；本项仅核查，不改变运行行为。

## 合同与现状

- 冻结列表要求 DeploymentAdmin Session/License、模板元数据分页；详情要求模板及当前版本信息与强 ETag。`PromptTemplateView` 允许身份、任务类型、状态、当前版本/schema/policy refs、hash/etag，禁止 Secret、固定客户资料和 Golden 答案。
- 当前数据库根表有 `template_state`、`active_version_no`、`lock_version`；不可变版本表有正文、hash、schema/policy refs。退役时保留旧指针作历史，但不能将其投影成“仍 ACTIVE”。
- 当前没有 Prompt 只读 Router、专属分页游标或 Windows Prompt 只读装配。现有 Model 读取链可作结构参考，但不得复用 Model 游标签名密钥或把 Prompt 正文混入普通元数据。

## 后续独立切片与验收

1. `P02`：专属 Prompt 列表 HMAC 游标及只读仓储/服务；游标绑定会话、查询、位置，按创建时间和 UUID 稳定排序。详情只投影允许字段；DRAFT/RETIRED 不假称活动版本，RETIRED 历史指针只在内部保留。授权和 License 在读取前校验。
2. `P03`：可选 HTTP LIST/GET，严格分页参数，统一错误与 `Cache-Control: no-store`，详情强 ETag；默认不挂载。合同与隔离 PG18 验证多状态、跨会话/篡改游标、无权/许可拒绝和正文/Secret 不泄露。
3. `P04`：独立 Prompt cursor 安全来源及 Windows 显式平台组合装配；缺密钥失败关闭，正式目标账户/发行信任和升级另验。

不需要新 Schema、Breaking API 或 Prompt 内容签名准入即可读取元数据；若实施时发现冻结 DTO 或信任机制冲突，应先另建 Change Request。不得从“只读通过”推断 AI Invocation 资格、正式 Prompt 内容准入、Gate3/UAT 或可用包通过。

验证：只读核对冻结 API/DM、ORM、现有 Model 读取与游标实现；无新增运行测试。回滚：本项仅文档，无运行回滚。
