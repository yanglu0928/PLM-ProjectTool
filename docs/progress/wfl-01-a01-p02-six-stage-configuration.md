# WFL-01-A01-P02：六阶段配置 V1

- Phase：2 Platform Core；前置 WFL-01-A01-P01 PASS。基线 V2.1 六阶段、DM-02、DM-05、API2-R04/API-04；先登记 CR-WFL-001，再实施。
- Changed/Files：`workflow/domain/catalog_v1.py`、单元测试、`docs/workflow/six-stage-definition-v1.md`、CR、STATUS、决策及版本说明。六阶段固定顺序，十二项 required，策略引用有来源；未知版本拒绝，不回退 latest。
- Migration/API/Permissions/依赖：无。没有项目实例、种子或用户正文；不改变实际客户事实。
- Tests：Windows 11/Python 3.13 后端 608 项无失败，2 项既有符号链接环境跳过。四项新增测试覆盖顺序/十二项/策略引用/不可变/未知版本失败关闭；开发 wheel 包含 catalog PASS，SHA-256 `2d0f5468367de938ecfdd05154aa23cf38733bdd8bf16f98f70e8d8abedb0f61`。
- Result：纯配置与文档验收 PASS；无数据库、API 或真实业务 Gate 验证。CR-WFL-001 配置补充落地，不修改原冻结 `64cdf09`。
- Known Issues：运行 Gate evaluator、授权 Owner/Evidence/Review 查询、状态持久化和 API 未实现，缺这些不得推进正式项目。NOT_REQUIRED 必须真实人工决定，AI 不可代签。Gate 3/可用程序包未完成；Server 2025 未运行，Debian 13 暂不验证。
- Next：WFL-01-A02-P01 状态及合法顺序推进纯领域规则前置检查，随后仍须独立持久化/权限/Gate/API 验收。
