# PLG-02-A06 Installation操作受控停用Owner结果

- 日期：2026-11-04
- CR：`CR-PLG-011`
- 代码提交：`50d25328e04e45dca90a58b5faea53d4a4a3140b`
- GitHub Actions：[Cloud sandbox validation run 41755590662](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41755590662)
- 结论：`PASS_SCOPE_LIMITED`

## 实施结果

为冻结的PLUGIN_DISABLE生命周期补充内部`PluginActivationOwner.disable`和严格的`DisablePluginInstallationCommand`。命令要求Installation ID、actor、trace和expected lock_version。Owner在既有plugin级锁与UoW中校验Package/Runtime事实，将当前所有操作置为DISABLED、清除EnabledOperation、为每项追加不可变History及Audit，并将Installation设为DISABLED、递增lock_version。精确版本、已DISABLED、无活动操作的重放返回无变化；陈旧版本、不一致状态、未验证Package/Runtime及已退役状态失败关闭。Audit写入失败时事务回滚。

没有新增表、字段、Migration、公开API或外部依赖。未连接默认生产组合、物理安装/卸载、插件子进程或PluginExecution。

## 独立验收

Hosted run 41755590662 的13/13 jobs成功。后端全量3,959 tests、wheel、前端测试/构建、PG18/pgvector、嵌入式后端与父包构建均通过。父包PG smoke artifact 13287594475在真实PostgreSQL 18.6临时数据库运行合成签名包/Installation事实：两项操作启用后停用，最终状态`DISABLED`、lock_version=2、活动操作=0、History=4、停用Audit=2；stale version被拒绝；Audit故障使状态、操作与History回滚；精确重放不产生写入。无客户数据、外部调用或生产数据库。

同run的父包SHA-256为`cfe8f74d3a1b8da7a76aa35e86baa8026e9148414c76c499e04de24baa3d1072`，20,173 files。A17 artifact 13288092884为合成托管Windows Server 2025流程，29 API调用、PlanVersion IN_REVIEW、客户决定0；A34 artifact 13288657373验证4个持久marker与显式人工恢复。A34产品服务未启动，正式License/公钥、数据库凭据、服务ACL/TLS仍阻断。

## 限制和偏差

本结论仅覆盖内部Owner与合成hosted PostgreSQL，不代表Windows 11实机、真实宿主安装/签名信任、客户验收、Pilot、Gate或正式Release。产品及测试代码没有在用户本机/C盘运行。

首轮PG smoke run 41754111643在A06集成步骤前被既有Pilot readiness PowerShell探针30秒超时终止；该环境偏差先记入CR-PLG-011，等待上限改为90秒后run 41755590662完整通过。Owner重放条件和签名夹具转义两个实现问题均先记录再修复，最终全量与PG18实测通过。
