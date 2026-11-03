# OUT-01-A01-P10：Plugin Operation生产能力事实Owner编码前核查

- 日期：2026-11-04
- 状态：PRECHECK_IN_PROGRESS（源码盘点尚未完成；未开始编码）
- WBS：OUT-01-A01-P10
- 依据：CR-OUT-004/007、P09 PASS_SCOPE_LIMITED、冻结API-03/DM-04

## 问题

OutputPolicy允许word.generate只是必要白名单，不能证明对应Plugin已安装、Operation已启用、签名/Publisher正式可信或运行条件满足。Output resolver要求operation registry返回enabled=true且trusted=true；缺失时必须失败关闭。

## 编码前检查

- 检查PluginPackage、Manifest operation/dependency、PluginInstallation、enabled operation、签名验证及publisher key trust的实际ORM/Owner/API/应用服务/组合根挂载状态。
- 区分VERIFIED、签名有效、已安装、安装有效、启用和正式publisher trust；确认任一状态是否有客户运行数据库可追溯事实，禁止从Manifest声明或开发者工作台资料推导客户启用/信任。
- 检查Windows packaged Plugin目录与A08 Worker的职责边界：异步验签/登记是否真正创建安装/启用记录；不存在时不得适配出enabled=true。
- 检查冻结Schema已有PLG-01/02/03字段能否满足固定operation lookup；若要增加安装状态或trust来源，识别是否触及冻结Data Model/DB Schema/License/安全架构，并先建立正式CR。
- 确定单一下一实现WBS及失败关闭边界；无真实信任材料时，适配器必须返回None/拒绝，不构造测试信任或启用事实。
- 不运行插件、不连接客户数据、不改状态/权限、不外发数据；源码盘点只读，代码和验证继续通过GitHub hosted runner。

## 验收与风险

P10盘点阶段不改代码或数据库。通过条件是明确一个现有受控事实Owner与只读内部适配范围，或证明当前没有可消费的生产事实并转向不依赖插件运行的独立Output文件渲染/Artifact设计任务。不可把Output链局部完成写成可用生成。

## 下一步

完成Plugin安装/启用/正式信任源码盘点后，记录CR-OUT-008并选择一个可客观验收的单项任务。
