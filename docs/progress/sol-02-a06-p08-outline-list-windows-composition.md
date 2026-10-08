# SOL-02-A06-P08 Windows 显式 Outline 列表组合

日期：2026-10-09。状态：Windows 11 隔离 ASGI/PostgreSQL 合成组合通过；正式目标账户/发行未验。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P08。
- 输入基线：冻结 `SOL_OUTLINE_LIST`；P04～P07 Owner、签名游标、Windows 独立 key ref 与可选 HTTP。
- 前置任务：P04～P07 验证通过，当前 Schema 0146。
- 模块/实体/API/权限：Windows 生产组合根、SolutionOutline LIST；冻结 GET；Session/License/当前项目成员，独立 cursor key 缺失则启动失败。
- 验收标准：登录专用模式404，只读/写显式平台模式挂载 LIST；写模式 CREATE 不被只读 POST 哨兵覆盖；缺 key/构造异常不发布半套 API、释放 runtime；Win11 隔离 PG/ASGI 三页可读。
- 风险：合成 License/密钥仅验证组合；正式服务账户 Vault/ACL/备份、Server2025 与 Release Gate 仍未验。

## 实施与验证

新增 `create_windows_outline_list_router`，强制使用 P06 独立 `OutlineListCursorCodec`。Windows 显式 `--platform` 与 `--platform-write` 在创建 License 服务后读取专属 Vault key 并注入列表路由；登录专用仍不挂载。写模式先挂载 CREATE，再挂载 LIST，使 POST 保持创建语义；只读模式 POST 仍404。无新 Schema/Migration/依赖或冻结 API 变化；撤下组合注入可回滚，历史保留。

- 定向 Windows/生产模式合同：39 passed / 20 subtests；含缺 key 和路由依赖失败、runtime 释放、三模式路由及 CREATE 不回退为404。
- Windows 11 隔离 PG18.6/ASGI：经 Windows 工厂真实 Session/三页 LIST、签名游标与拒绝路径通过；临时库/实例由夹具清理。
- 后端全量回归：3386 passed / 3 skipped / 5095 subtests passed。

下一项：`SOL-02-A06-P09` 方案大纲前端只读列表/详情与创建后定位；随后真实浏览器/隔离 PG 验证。正式服务账户密钥、非空批准链、20并发与发行仍待。
