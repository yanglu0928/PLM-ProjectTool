# SOL-04-A21：Windows 11 Edge／隔离 PostgreSQL Section 联测

日期：2026-10-09。结果：`SOL_04_A21_SECTION_EDGE_PG_PASS`，限 Windows 11、一次性 PostgreSQL 18.6、合成身份与独立 Edge Profile；不代表正式发行、真人确认或 Gate 3 通过。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A21。
- 输入基线：冻结 `SOL_SECTION_CREATE/GET/LIST`、A04/A08/A14 后端 HTTP、A15 Windows 组合、A17～A20 前端客户端/页面。
- 前置：后端真实 Session/PG 创建与读取、前端创建/读页面合同已通过。
- 模块/实体/API/权限：仅一次性验证夹具；Section/Outline 身份；现有 POST/GET/LIST；浏览器 PM 创建、客户角色只读，服务端复验。
- 验收：Edge 登录、活动父目录核对、Section CREATE 后详情/列表、故意丢失首次 201 后刷新同键恢复、单一数据库身份/审计、客户页面隐藏写入口和真实 HTTP 拒写；隔离资源清理。
- 风险：CDP 等待时序/浏览器进程清理，正式 License/目标账户、Server2025、性能、Gate3/UAT 未测。

## 证据

一次性 PG18.6 经现有夹具 Alembic head 建库；新建两名合成用户，口令每次运行临时生成且不写入仓库。显式挂载 Windows Outline/Section 创建、详情、独立签名列表及 Project/Session 路由。独立 Edge Profile 通过页面登录，先创建活动父目录，再创建 Section。CDP 在服务端返回 Section 201 后仅丢弃该响应；页面显示结果不确定并保留原操作号。刷新并重新登录后父目录再次核对，章节键锁定，明确勾选后同键重试进入详情，再回项目级列表可找到同一章节。SQL 核查 `Browser Section` 仅一条、`SOL_SECTION_CREATED` 审计仅一次；客户角色可读列表但无创建入口，独立真实 HTTP POST 返回 404 `RESOURCE_NOT_FOUND`。脚本退出 0，报告 `SOL_04_A21_SECTION_EDGE_PG_PASS`；一次性库和浏览器 Profile 由夹具清理。

首轮浏览器脚本在列表标题出现即点击写入口，链接尚未渲染而退出 1；改为等待写入口。第二轮从详情回列表时旧页面仍有 `Browser Section` 文本，等待条件过早返回；改为等待目标 URL 与具体 Section 链接。第三轮整体退出 0；移除固定合成口令后第四轮重新运行仍退出 0。此前失败不充当通过证据。

兼容/迁移/回滚：仅新增隔离验证夹具，无正式程序、Schema/Migration、依赖或冻结 API 变化；删除夹具可回滚。已知边界：合成 License/服务账户，不覆盖非空审批链、客户真人确认、正式公钥/Vault/HTTPS、Server2025、20 并发、Gate3/UAT/发行；Debian13 实机依用户指令暂跳过。下一项转向 `SOL-01-A05` Reference Revise/Eligibility 前置核查，为 OutlineVersion 的合格来源建立真实证明；Outline PATCH/ARCHIVE 与 SectionVersion 仍独立待办。TraceLink：Gate 2/API-04 → A15/A20 → A21 → SOL-01-A05/SOL-03。
