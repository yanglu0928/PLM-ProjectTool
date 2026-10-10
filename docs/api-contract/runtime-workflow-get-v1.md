# 运行 Workflow GET V1

版本 0.1.0.dev0；日期 2026-09-26；WFL-01-A04-P02。实现冻结 API-02 `WORKFLOW_GET`，不改变原冻结合同或阶段定义。

- GET `/api/v1/projects/{project_id}/workflow`；Operation ID `WORKFLOW_GET`。只接受路径 UUID，不接受查询参数。
- 校验可信 Host、HttpOnly Session Cookie 和当前数据库 Session/User，受控 License、项目成员事实与完整固定 Workflow 投影。PM/IM/CustomerManager/CustomerMember 可读，归档可读；无项目成员资格的部署管理员不能获得访问。GET 不要求 CSRF 写令牌。
- 成功 200：`data` 包含 workflow_id、version（定义版本）、state、current_stage、stages、etag；Stage 包含 stage_key/order/state/checklist_items；Item 只含 item_key/required/state。`trace_id` 为当前请求标识。
- Header：ETag 为当前 Workflow 锁版本，例如 `"v0"`；Cache-Control 为 no-store。不返回内部 lock_version 列、ProjectId 副本、fingerprint、GatePolicy/ReviewPolicy 内部引用、数据库/存储定位或原文。
- 错误：缺失/失效 Session 401；可信 Host 或 License 拒绝 403；无权/跨项目/缺实例 404；非法参数 400；内部服务/畸形或错误项目投影 503。所有错误保持注册错误包络，不返回 traceback、内部错误详情或资源内容。
- 缺实例不自动初始化、不写审计、不推断当前进度；定义版本与锁版本不同。GET 描述当前存储状态，不证明客户 Review/Gate。
- WFL-01-A04-P03 已挂入 Windows 显式 `--platform` / `--platform-write` 组合，复用当前 Session/项目授权/License 和既有信任源检查。默认应用/仅登录组合仍不挂载；Workflow 写/start/transition 路径仍未实现，不能凭读 API 关闭 Workflow/Gate。缺信任源时拒绝启动，不降级为无保护读取。

Windows 11/Python 3.13 后端 641 项无失败（2 项既有符号链接环境跳过）；真实 PostgreSQL/Session HTTP 与白名单/拒绝边界、开发 wheel PASS。合成 License 不证明正式发行信任源；Server 2025 未运行、Debian 13 暂不验证。
