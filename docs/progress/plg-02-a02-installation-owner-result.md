# PLG-02-A02：Installation事实Owner云端验收结果

- 日期：2026-11-04
- 结论：`PASS_SCOPE_LIMITED`
- 范围：内部记录已由安装适配器核实的初始 `INSTALLED` 事实；不包含物理文件部署、API、启用、插件执行或正式信任。
- 代码提交：Owner `0534e041c520e5e0d0cdbe8e51eaf82adcc241f1`；head契约修正 `b66aa987db8387041aa48be2aa2f6a8a324deed3`；PLG-01父包验证器同步 `958ad743252dd11735db1cc0f56efb2b29fa9169`。
- 编码前检查：`docs/progress/plg-02-a02-installation-owner-precheck.md`
- 变更与偏差：`docs/changes/CR-PLG-007-plugin-installation-persistence.md`

## 实现

- 新增内部 `PluginInstallationOwner`：固定installation ID重放幂等；不同Package或Actor复用ID时冲突；只接受 VERIFIED Package、受控证据端口核对的精确Package ID/SHA-256、兼容宿主快照；排除路径等未批准字段。
- 在一个Unit of Work内写入初始Installation、兼容性验证历史及Audit；Audit或数据库失败会回滚。Owner没有加入HTTP API或默认组合。
- Migration `20261104_0226` 将A01的全关闭写守卫收窄为：仅Installation与RuntimeValidation允许事务局部标记下的INSERT；仍拒绝所有UPDATE/DELETE/TRUNCATE，EnabledOperation全程保持关闭。有记录时拒绝降级。
- 修正两个随head递增未更新的旧验证边界：backend migration contract和PLG-01 parent PG验证器；均先在CR记录失败，再更新版本期待。保留0224历史边界。

## 云端验收

- GitHub hosted workflow [41721092729](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41721092729)：13/13 jobs成功。
- 后端3,932项测试、backend wheel、前端全量/build、PostgreSQL 18.6/pgvector sidecar、Windows embedded backend/父包候选、临时PG生命周期smoke、A17、A34、A35与A50均成功。
- 隔离PG18.6 smoke确认当前head 0226、空库upgrade/downgrade/re-upgrade、既有PLG-01数据保留、Owner未经事务标记时拒绝写入、标记内的合成Installation/RuntimeValidation登记、状态/关系约束及有历史降级拒绝；所有数据库均为临时合成库。
- 同run父包候选20,164项，SHA-256 `4305e24a632acef0cd690612a8a9a2b5e620c2e022a5284ca265f9019b86783a`，仅内部非发行候选。runner工作盘D:。
- 客户数据0、外部API调用0、生产数据库false、产品API/监听false、license trust未使用、生产安装false。

## 限制

- 所有代码与测试仅在GitHub hosted Windows runner D盘运行；没有在用户本机执行项目代码或测试。
- 托管用合成端口和合成记录证明边界，不代表已有真实安装适配器；Owner当前未接入生产组合，不能从Package VERIFIED推断已安装。
- 本项不验证Windows 11实机安装，不关闭Gate/Pilot/Release。正式数据库身份隔离、安装适配器、公开用户入口和启用状态转换仍需后续WBS。
- 初次后端单测运行及旧PLG-01父包验证器版本偏差均已按“先记CR、再修复”追溯。

## 下一项

PLG-02-A03：核对冻结启用操作/安装状态变更规则与事务边界，完成编码前检查后实现启停Owner。不得执行插件子进程或将启用等同于安全执行许可。
