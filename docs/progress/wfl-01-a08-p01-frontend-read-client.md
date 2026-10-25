# WFL-01-A08-P01：Workflow 前端固定快照只读客户端

2026-10-02 / Phase 2 / `FRONTEND_CLIENT_PASS`。编码前检查：Gate 2 `WORKFLOW_GET`、六阶段 V1、Windows 显式平台已有受权 GET、前端 Session 与 Project 路由基础具备。仅新增未接页面的只读客户端，不新增写按钮、权限推断、API/Schema/依赖或 Stage Gate 事实。

实现：限定规范非零 ProjectId，发送同源、无缓存、无重定向 GET；只接受 JSON/TraceId/200 与响应体强 ETag 一致。对白名单六阶段顺序、十二 required 清单、状态/当前阶段关系进行结构校验，输出冻结的最小展示字段；已知 401/403/404 映射为安全提示，未知/异常/超时失败关闭，不显示服务端私密异常。该快照仅是当前查询结果，不能当客户批准或 Gate 证据。

验证：新增定向测试覆盖固定初态/ACTIVE/COMPLETED、ID、状态/顺序/清单/ETag、不一致响应、错误码及网络异常；前端全量59文件1171项、typecheck、production build通过。当前任务未做浏览器页面或真实网络/PG前端端到端；现有非发行包不含本项。

兼容/升级/回滚：未连接页面，不改变现有 UI、后端或迁移；可撤客户端不影响业务数据。下一项把受控 Workflow START 请求桥接至 SessionClient，再做启动回执客户端及项目页面。正式信任、真实浏览器、Server2025/Debian、A07 Owner/Stage Gate、UAT/Gate3仍开放。
