# EVD-01-A04-P03-A08-P07：原操作者收据只读查询

日期：2026-10-01；Phase 2 Platform Core；结果：`UNIT_SQL_PASS / REAL_PG_OPEN`。

编码前检查：输入 CR-EVD-004、现有 `0015` 通用幂等收据表与 `SqlAlchemyIdempotencyReceipts`；设计已先登记并推送。范围只涉及 Platform 收据仓库的只读方法与单测。无新实体、Migration、API、权限或依赖；调用方必须先证明当前 Session/角色/资源归属。验收为 actor/project/operation/key digest 全域查询、只投影已完成结果、不加锁/不 autoflush/不写库、缺记录返回 None、PENDING/畸形/数据库故障失败关闭。风险是 None 可能表示尚未提交而非明确失败。

新增 `lookup_result`，区别于写命令的 `lookup_completed`：不需要重传包含理由的 payload fingerprint，也不改变后者的同 Key/同 payload 冲突保护。仓库只返回 `IdempotencyResult` 或 None；不返回原 Key、指纹或正文。代码没有挂到 HTTP，也不能单独作为授权证据。

定向单测9项 PASS（含新增只读查询4项）；Windows11/Python3.13 后端全量1,801项 PASS、3项既有环境跳过；开发 wheel 构建 PASS，SHA-256 `f81afaee2c4484ae69a872c08f47e3064850598eba33f95eec9b7ffaa94038cc`。首次 `python -m build` 因测试虚拟环境未安装 build 模块退出1，改用已有 pip 的 `pip wheel --no-build-isolation --no-deps` 成功；未为此增加生产依赖。实际 PostgreSQL 提交/回滚/并发可见性、当前身份授权、HTTP 与平台装配仍未验。

兼容/升级：复用 `0015`，无 Migration；撤销新方法可回滚，不删除既有收据。下一项先实现 Evidence 层当前身份和 Scope 只读授权/存在性证明，再组合服务，不从 API 直接读 Platform 表。Gate3与可用程序包仍开放。
