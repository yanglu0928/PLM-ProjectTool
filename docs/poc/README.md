# Phase 0 技术验证

本目录保存 Phase 0 的执行登记、环境矩阵和各 PoC 的正式证据索引。PoC 实现、输入和可重复执行脚本位于仓库根目录的 `poc/`。

## 当前状态

- Phase：Phase 0
- 状态：IN_PROGRESS
- 启动日期：2026-09-17
- 当前任务：POC-02 PostgreSQL 18 + pgvector（Windows 11 功能链已通过，待断网及另两平台验证）
- 正式业务开发：BLOCKED

## 入口

- [Phase 0 执行登记表](phase-0-execution-register.md)
- [三平台环境矩阵](environment-matrix.md)
- [POC-01 实施与结果](../../poc/poc-01-python-313-dependencies/README.md)
- [POC-02 实施与结果](../../poc/poc-02-postgresql-18-pgvector/README.md)
- [Phase 0 验证例外](phase-0-exceptions.md)

## 判定规则

每个 PoC 必须具备 README、Environment、Input、Steps、Result、Metrics、Logs、Known Issues、Conclusion、PASS/FAIL 和 Alternative。缺少任一项时不得标记完成。

所有结论必须由可重复执行的日志和指标支持。Windows 11、Windows Server 2025、Debian 13 原则上必须分别形成正式验证证据；一个平台的结果不能代替另一个平台。经用户明确批准暂缓的平台必须登记例外，并保持“未验证”标识。
