# CR-HND-007：Handover 三类 Cursor Key 的生产仪式前置

日期：2026-10-05。状态：机制已实施并以隔离合成 Key 验证，正式目标服务账户仪式待 Release。关联 `HND-01-A05-A07`、DEC-20261005-875 与 Windows 生产组合；不改写 Gate 2 原冻结提交 `64cdf09`。

## 偏差

冻结 API 要求 Analysis、Version、Item 三类分页 cursor 能被生产入口安全签名和校验，但当前开发者账户没有为正式 Windows 服务账户完成三把独立 Vault key 的生成、双人备份、ACL、恢复演练和轮换记录。把测试 Key 写入配置、仓库或发行包会把验证材料误作生产 Secret；复用其他 cursor key 则会扩大跨资源重放面。

## 方案

- 生产组合固定使用 `handover-analysis-cursor-v1`、`handover-version-cursor-v1`、`handover-item-cursor-v1` 三个独立引用，并要求每把 key 至少 32 字节。
- 任一引用缺失、过短或解析失败，显式平台模式拒绝启动；不降级为无签名、共享 key、临时随机 key 或默认常量。
- Windows 11 客观验证通过仅存在于验证进程内的三把合成 key 完成；不写文件、不写数据库、不进入 Git 或 wheel，也不形成正式服务账户已配置的事实。
- Release 前必须针对实际服务账户完成生成、备份、最小 ACL、恢复与轮换演练，并把仅含引用和证明的记录纳入发行检查；Secret 内容不得进入证据或日志。

## 影响、迁移、回滚与验证

无 Schema/Migration、冻结 API、依赖、网络或客户数据外发变化。显式只读平台模式挂载五个 GET；显式写平台模式另挂载五个普通命令和业务原子送审；默认/login-only 仍关闭。撤除 Handover 组合注入可恢复 404，既有业务历史不删除。

验证结果：Windows 11 / PostgreSQL 18.6 真实 ASGI/HTTP 链覆盖 11 个 Analysis Operation、三类分页、原子送审/重放、通用 Review 批准、批准后首回执恢复、升版/再次送审/撤回和 Alembic drift=0；后端全量 2706 项通过、3 项环境条件跳过；开发 wheel SHA-256 `0d909a2ca641c1ef8b8fd3f17d847dc302a37f95a8aef28339b6c0c83a8469c7`。正式目标账户仪式未完成，不能据此关闭 Release/Gate 3。
