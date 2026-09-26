# CR-AUD-003：审计导出结果与内容 HTTP 增量

日期：2026-09-26。状态：AUTHORIZED_CONTINUOUS_EXECUTION / IMPLEMENTATION_IN_PROGRESS。
来源：持续交付授权、STATUS P03-A06；冻结 API-02 提交导出和 API-03 JobView 结果引用没有专用结果/内容 GET。原冻结提交 64cdf09 不改写。

比较：静态文件 URL 无法保证当前会话和项目隔离，不采用；借用普通 DocumentVersion 会伪造业务引用，不采用；新增只读 Audit 专属 GET，复用 P03-A05 实际成功来源和当前授权，选用。

差异：增量增加 PROJECT 与 DEPLOYMENT 结果/内容 GET，不改变已有请求或响应；不新增 DB、依赖、角色、产品权益或业务 Scope。Admin 没有项目访问旁路。详情只返回白名单成功元数据，不能把内部结果 DTO 或 manifest 原文序列化给客户端。

实施顺序：P03-A06-P01 契约与可选结果详情 GET；P02 可选内容 GET、并发限额、断连/异常/取消清理；P03 实际 PostgreSQL/文件 HTTP 验证与显式 Windows 组合。未完成阶段不声明通过；默认应用保持 404，POST 尚未接线。

风险：内部路径、原提交者/Worker/租约和 manifest 泄漏；旧权限重用；私有快照未关闭；大文件并发资源。控制：显式投影、每次调用当前 Session/License/角色与实际成功来源重核、下载完整 Hash 和复制后二次授权、有界准备/传输与所有退出分支清理。

迁移：无 Schema/数据迁移。升级仅增加 opt-in Router 参数。回滚卸载路由，保留已有成功文件和不可变历史；不删除已发布成果。验收：默认关闭、双 Scope、路由坐标重核、真实会话/许可/项目权限、错误合同、不返回内部字段、HTTP 无业务写；下载另外验证真实字节、复制后撤权与断连/取消资源释放。

契约：docs/api-contract/audit-export-read-v1-increment.md。剩余风险：正式信任源、目标账户/三平台、Worker 心跳及性能、整体质量和 Release Gate 未关闭。

实施记录：P03-A06-P01可选两详情GET已实现；4契约测试、真实PG已发布双Scope/当前Session权限与无业务写验证PASS，全后端955项无失败（2既有环境跳过）、开发wheel成功。无Migration/依赖/生产组合，原API保留。下载/生命周期/P03装配尚未实施，CR整体不标完成。详见对应进度记录。

P02实施记录：两内容GET已实现；准备/读线程取消的显式资源所有权与Response外层finally，取消不提前释放活跃线程名额；7契约/ASGI tests与实际PG/文件双Scope空/260字节/Hash/权限/复制后撤销/坏文件最小Audit通过。全后端962无失败（2环境跳过）、wheel成功。无Migration/依赖，默认404，生产组合留P03；真实代理/目标账户/三平台/性能未验，整体CR不标完成。
