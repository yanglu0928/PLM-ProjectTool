# PLG-02-A05 Installation退役终态Owner结果

- 日期：2026-11-04
- CR：`CR-PLG-010`
- 代码提交：`358483d626c88a1e9ef1ccfcdf3e99de7db7546c`
- GitHub Actions：[Cloud sandbox validation run 41743782405](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41743782405)
- 结论：`PASS_SCOPE_LIMITED`

## 实施内容

新增内部Installation退休Owner和PostgreSQL repository。命令在同plugin级事务锁下检查Installation身份与expected lock_version。对于每个启用操作，在同一事务写DISABLED Audit与不可变History；写Installation级RETIRED Audit后清除当前操作、将Installation单向设为RETIRED并递增版本。无操作安装可直接退役；已退役、陈旧版本和不一致状态失败关闭。数据库Migration `20261104_0229`要求退役Audit与无活动操作，并拒绝RETIRED状态回退。

不新增表、字段、API或外部依赖。未接生产/默认组合，未物理卸载或删除Package、Installation、History、Audit及既有OutputArtifact；没有启动或执行插件。

## 验收证据

同提交 hosted run 共13/13 jobs成功：后端全量3,955 tests及wheel、前端测试/typecheck/build、PG18.6/pgvector组件、嵌入式后端/父包、A35/A17/A34/A50链。PG smoke summary artifact 13283431324 显示schema head 0229、退役守卫PASS、空库全链升降重升通过、带PLG-02历史拒绝降级且保留行事实；父包archive SHA-256 `81b1425c2ffa866f43b96ebc744bec0cbef8332b090c9d7cab746dc58e016515`、20,173文件。

A17 artifact 13283911131 验证同包Edge/HTTPS/隔离PG PlanVersion流程（29 API调用，状态IN_REVIEW，客户决定0），仅hosted Windows Server 2025 synthetic环境。A34 artifact 13283696477 验证失败候选隔离、4个marker保留和显式人工恢复；其产品启动仍被正式License/公钥、数据库凭据、ACL、TLS前置阻断，服务未启动。A35候选交接及A50 Edge检查通过。

## 限制与后续

此项不等于Windows 11实机、物理安装/卸载、公开API、真实插件信任、插件执行或正式Pilot/Gate/Release通过。无客户数据、外部API和生产数据库。本机/C盘未运行项目代码或测试；所有执行由GitHub hosted runner完成。

下一项PLG-02-A06：Plugin生命周期受控组合与宿主适配器编码前检查，先核对冻结API、生产身份、真实安装证据与信任边界。
