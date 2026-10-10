# CR-DOC-008/A02-P01：Content 全窗口栅栏

- 日期：2026-09-26；结果：Windows 11 内部 Content 与显式写模式栅栏接入 PASS；Commit/Abort/清理尚未接入，物理清理仍关闭。
- 基线：ADR-008、`CR-DOC-008`、A01 本地跨进程 OS 栅栏。Content Service 必须注入栅栏，规范请求校验后、第一次许可/数据库预检前获取；直到流接收/临时文件校验与最终数据库事务完成才释放。争用失败映射既有 `FILE_CONTENT_UNAVAILABLE` 安全响应，不开始数据库预检，也不暴露锁路径。
- Windows `--platform-write` 组合在挂载 Content 路由前构建同一数据根的栅栏；栅栏不可用则整模式失败关闭。普通与只读模式不扩大写接口。
- 验证：Windows 11/Python 3.13 Content 单元覆盖持锁预检/接收及异常释放、争用时不访问数据库；隔离 PostgreSQL 18.6/临时文件原内容接收/重放/拒绝集成脚本 PASS；后端全部 547 项无失败（2 项既有符号链接环境跳过），开发 wheel PASS。尚未做 Content 与 Commit/Abort 交叉并发验证。
- 无 Migration、新依赖或冻结 API 修改。版本 `0.1.0.dev0`。回滚须先停写；删除此注入后不得开启清理。
