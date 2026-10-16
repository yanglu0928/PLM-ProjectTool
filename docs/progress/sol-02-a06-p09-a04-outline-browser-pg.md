# SOL-02-A06-P09-A04：Windows 11 Edge／隔离 PostgreSQL 方案目录联测

日期：2026-10-09。结果：`SOL_02_A06_P09_A04_OUTLINE_EDGE_PG_PASS`，限 Windows 11、一次性 PostgreSQL 18.6、合成身份与独立 Edge Profile；不代表正式发行、真人确认或 Gate 3 通过。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P09-A04。
- 输入基线：冻结 `SOL_OUTLINE_CREATE/LIST/GET`、后端 A03～A05/P01～P08、前端 P09-A01～A03。
- 前置任务：后端真实 Session/PG 创建与读取组合、前端创建/读页面合同均通过。
- 模块/实体/API/权限：仅一次性验证夹具；SolutionOutline；现有 POST/LIST/GET；浏览器项目负责人创建、客户角色只读，服务端复验。
- 验收标准：真实浏览器登录、创建后详情/列表、故意丢失首次 201 后刷新同键恢复、单一数据库身份/审计、客户角色页面和网络拒写；夹具清理隔离资源。
- 风险：CDP 响应拦截与浏览器进程清理时序；正式 License/目标账户、Server2025、性能、Gate3/UAT 未测。

## 证据

一次性 PostgreSQL 18.6 经 Alembic head 建库；新增两名合成用户，不修改原夹具的不可变密码历史。显式挂载 Windows Outline 创建、详情、签名列表及 Project 读取/Session 路由。独立 Edge Profile 通过页面登录，创建时 CDP 在服务端返回 201 后仅丢弃该响应；页面显示结果不确定并保留原操作号。刷新后重新登录，原名称被锁定、须明确勾选后重试；第二次请求复用相同幂等键，进入详情，返回列表可再次打开同一目录。数据库中 `Browser Outline` 仅一条，`SOL_OUTLINE_CREATED` 审计仅一次。客户角色可读列表但无创建入口；独立真实 HTTP POST 返回 404 `RESOURCE_NOT_FOUND`。脚本退出 0，夹具报告 `SOL_02_A06_P09_A04_OUTLINE_EDGE_PG_PASS`。

首轮夹具尝试修改已有密码凭据，因历史不可变约束被拒绝；改为创建独立合成用户。第二轮浏览器业务路径通过，但 Edge Profile 文件仍被进程占用，清理报 `EBUSY`、退出 1；加入进程退出等待与受边界检查的重试清理，第三轮整体退出 0。首次失败所留旧 Profile 的单独清理请求被环境策略拒绝，未绕过；路径 `C:\Users\17231\AppData\Local\Temp\plm-outline-edge-KAqzO7` 可能仍存在，不在仓库和发行包内。

兼容/迁移/回滚：仅新增验证夹具，无正式程序、Schema、Migration、公开 API 或依赖变化；删除夹具可回滚。已知边界：合成 License 与服务账户，不覆盖非空审批链、客户真人确认、正式公钥/信任源、Server2025、20 并发、Gate3/UAT/发行；Debian13 实机按用户指令暂跳过。下一项 `SOL-03-A01`：目录 Version 正式受控写入前置核查，先核对现有 0137 Schema Guard、冻结来源/Review/Trace 合同与迁移风险。
