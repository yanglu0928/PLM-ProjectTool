# HND-01-A05-A07：Handover Analysis Windows 生产组合

日期：2026-10-05。结论：`HND_01_A05_A07_WINDOWS_COMPOSITION_PASS`（隔离合成 cursor key）。下一项：`HND-01-A06-A01` 前端与交互前置核查。

## 实施结果

新增 Windows Handover 组合根并接入显式平台入口。只读模式仅挂载 Analysis LIST/GET、Version LIST/GET、Item LIST 五个 GET；写模式在此基础上挂载 Analysis CREATE/PATCH/ARCHIVE、Version CREATE/VALIDATE 五个普通命令及 Version 业务原子送审。通用 Review 和 Handover Action 继续由各自 Owner/Router 负责，没有在组合层复制业务事实。

组合固定解析 Analysis、Version、Item 三个独立 cursor key 引用；任一 key 缺失或不合格即拒绝启动。按 CR-HND-007，本轮真实链使用仅存在于验证进程的隔离合成 key，未落盘、未入库、未打包；正式服务账户的生成、备份、ACL、恢复和轮换仪式仍是 Release 前置条件。

## 客观验证

- 新增组合单元 2 项及生产入口相关合同 32 项通过，覆盖 read/write 路由矩阵、三 key 缺失失败关闭和既有入口装配。
- Windows 11 / PostgreSQL 18.6 真实 ASGI/HTTP/数据库链通过：五个读取、五个普通命令、业务原子送审共 11 个冻结 Analysis Operation；覆盖 Analysis 分页续页、送审即时重放、通用 Review 批准、批准后首次回执恢复、第二版送审/撤回及 Alembic drift=0。
- Windows 11 / Python 3.13 后端全量 2706 项通过，3 项环境条件跳过。
- 开发 wheel 包含 Windows Handover 组合、读/写/cursor/送审模块，SHA-256 `0d909a2ca641c1ef8b8fd3f17d847dc302a37f95a8aef28339b6c0c83a8469c7`。

## 兼容、回滚与未关闭项

无 Schema/Migration、冻结 API、依赖、外部网络或客户数据外发变化。停止注入组合 Router 即恢复关闭，合法 Analysis/Version/Review/Audit/收据历史保留。

本结论只证明 Win11 隔离验证和失败关闭装配；正式目标账户 key 仪式、前端/浏览器闭环、Windows Server 2025、Gate 3、UAT 与正式发行仍按总状态跟踪。Debian 13 按用户指令跳过实机验证，但仍是正式兼容目标。
