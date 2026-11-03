# PLG-02-A02：Installation事实Owner编码前检查

- 日期：2026-11-04
- 状态：PASS_WITH_LIMITATION（仅限事实Owner，不代表物理安装）
- WBS：PLG-02-A02
- 变更记录：CR-PLG-007
- 基线提交：b59560fbe294088c45861732e8cd989a44d23fbf

## 检查结论

- 冻结Data Model规定PluginInstallation精确引用Package，状态使用`INSTALLED / ENABLED / DISABLED / INCOMPATIBLE / RETIRED`，并保存已验证运行时快照与责任人/时间；同一插件操作至多一个Installation启用；运行环境兼容性失效时必须停止新的Execution。
- A01已实现三张表，但数据库触发器仍关闭所有写入；没有Installation业务Owner、安装文件部署执行器、安装API或运行时执行入口。PLG-01目前只确认并登记包元数据，不能把VERIFIED推断为已安装。
- 本WBS边界定为“记录经受控内部安装端口核实的安装事实”：只允许新建`INSTALLED`事实及对应兼容性快照，必须由端口核实精确Package仍为VERIFIED且未撤销、安装包Hash一致、宿主运行时兼容。安装/验证/Audit需在同一数据库事务成功；调用重放以调用方固定installation id幂等，异内容冲突。
- 安装事实Owner不负责复制/解压包文件，不切换ENABLED，不写enabled_operations，不支持版本切换，不创建API/默认组合，不提供运行时信任，不执行插件。没有可提供安装事实的受信适配器时，正式组合保持不可用；合成端口仅用于托管验收。
- 偏差：A01的全表关闭触发器必须为两张Owner目标表开放“仅由事务局部上下文授权的INSERT”，仍拒绝UPDATE/DELETE/TRUNCATE；enabled_operations继续完全关闭。此DB标记是应用写路径约束，不替代正式数据库身份隔离。Migration `20261104_0226`作为向前兼容增量，Down遇到历史记录失败关闭。
- 不更改冻结Data Model/API，不增加外部依赖。风险是内部端口与数据库会话写标记仍须后续通过受控组合、真实身份、权限验证加强；未配置真实安装适配器不产生生产事实。
- 验收：仅GitHub hosted Windows runner D盘临时工作区及合成PG18.6。覆盖包状态/撤销、兼容/Hash错误、精确Actor、固定ID重放及冲突、Audit失败回滚、未授权写、UPDATE/DELETE/TRUNCATE拒绝、空库升降重升及有事实降级拒绝；运行完整CI/A17/A34。用户本机不运行代码或测试。

## 前置检查结果

通过本项有界Application Owner实现前置检查。实现后只可得`PASS_SCOPE_LIMITED`，除非独立WBS接入并验证实际包部署、正式服务身份与用户入口。不得据此宣称物理安装、插件启用、正式信任、Gate/Pilot/Release通过。


## 首轮云端偏差（修复前记录）

- Run [41717001638](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41717001638) 后端3,932项仅有一项失败：migration contract仍期待0225，而当前迁移head已按本WBS前置记录升至0226。前端、PG18 sidecar、Python base及A50通过；下游组装/父包/A17/A34跳过。
- 失败是历史测试基线未更新的明确版本边界，不改Owner逻辑或冻结基线。先登记在CR-PLG-007，再仅修正预期migration head并重跑完整托管验收。
