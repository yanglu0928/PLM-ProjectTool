# SUR-01-A05-A04：Survey 五个普通写 HTTP

日期：2026-10-06。结论：`SUR_01_A05_A04_COMMAND_HTTP_PASS`。下一项：`SUR-01-A05-A05` SurveyVersion 原子送审。

## 编码前检查与范围

冻结 API-04 已定义 CREATE、PATCH、ARCHIVE、VERSION_CREATE 和 VERSION_VALIDATE 五个 Operation；A02/A03 已提供读取、创建、状态、版本创建和当前事实校验 Owner。本项只建立可选 HTTP 边界和 `create_app` 显式注入点，不装入 Windows 生产组合，不提前实现原子送审、读取 cursor 或 UI。与冻结路径及已实现 Owner 一致，无需新 Change Request。

Router 实施信任 Origin、Session/CSRF、License、幂等键和强 If-Match 边界；严格限制 UTF-8 JSON、2 MiB、重复/未知字段、规范 UUID 和无 query。SurveyVersion DTO 将问题、选项、条件、四类类型化来源与目标部门映射到内部不可变快照，不返回跨模块正文或路径。权限与隔离继续由 Owner 事务内重验，Router 不重复业务规则。

## 兼容、回滚与验证

无 Schema/Migration、ORM、依赖、配置、Secret、网络或外发变化；Schema head 保持 0106。默认组合五路径均 404，可通过停止注入 Router 回滚，不删除已有合法历史。

- 定向17项通过：五端点成功返回、默认关闭、Origin/Session/CSRF、幂等键、If-Match、query/JSON/UUID负例和安全错误投影。
- 首次全量误用早期精简虚拟环境，因缺 `pgvector` 产生19个导入错误，不计产品证据；改用完整 Python 3.13 依赖环境后后端全量 2832 项通过、3 项跳过。
- wheel 内含 Survey API 包标记、commands Router 和新组合入口，1047 entries；SHA-256 `7b1f6ffdaf5cc9b4c5e4aa70b8e309f5db56bfe11cace2004663a90b0244b374`。

已知未完成：A05原子送审、A06四读HTTP/cursor、A07 Windows真实HTTP/PG组合；Survey Round/Response/Conclusion、Server 2025、Debian 13实机、Gate 3、UAT和发行验收仍按总状态跟踪。
