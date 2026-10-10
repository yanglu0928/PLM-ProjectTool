# SOL-01-A04-P07-P02：PROJECT Reference 前端只读客户端

日期：2026-10-09；结果：`REFERENCE_FRONTEND_READ_CLIENT_PASS`。输入为冻结 API-04、CR-SOL-008 及 P07-P01 GET/List 后端投影。前置后端 Owner/HTTP/Windows 隔离 PG 组合已通过。模块只涉及前端 Solution 读取客户端，不修改实体、Schema、权限或服务端 API。

客户端提供 PROJECT List 和当前详情，强约束规范 UUID、页大小/不透明游标、同项目身份、有序唯一摘要、固定 Document 根/版本配对、Evidence ID、内容指纹、强 ETag 一致性及有限可展示适用性对象。异常数据失败关闭，不接收额外字段或来源路径，不将历史引用状态解释为当前来源有效。请求使用同源 Session Cookie、`no-store`、禁止重定向；已知 Session/License/404 错误给出安全提示。

定向 3 测试、前端全量 `102 files / 1608 tests`、TypeScript 类型检查和 Vite 构建均通过。构建保留既有主包超过 500 kB 警告；客户端尚未接入页面，因此本项不声称界面或浏览器 UAT 完成。无数据升级；回滚为移除未挂载客户端。正式 License/服务账户、Server 2025、20 并发、Gate 3 与可用程序包未验。Debian 13 依用户指令跳过。

TraceLink：API-04 → CR-SOL-008/P07-P01 → P07-P02 客户端/定向/全量/构建 → P07-P03 页面。
