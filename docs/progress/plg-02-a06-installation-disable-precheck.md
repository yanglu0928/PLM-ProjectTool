# PLG-02-A06：Installation操作受控停用Owner编码前检查

- 日期：2026-11-04
- 状态：`PASS_WITH_LIMITATION`（范围已定；尚未编码与验收）
- WBS：PLG-02-A06
- 变更记录：`docs/changes/CR-PLG-011-plugin-operation-disable.md`
- 前置：PLG-02-A01～A05均以`PASS_SCOPE_LIMITED`完成

## 核查结论

冻结API Contract V1的Plugin生命周期包含`PLUGIN_ENABLE`、`PLUGIN_DISABLE`和`PLUGIN_RETIRE`。现有`PluginActivationOwner.enable`能按Manifest子集原子替换操作并在冲突时移除旧安装操作；A04运行时复验会在不兼容时撤销启用操作，A05可退役安装。但没有独立的人工DISABLE命令可供冻结API的停用操作调用。

生产Windows显式写组合已经装配包导入HTTP和后台验签/登记Worker。Package登记只证明签名、Hash、Manifest和兼容性检查通过，明确不证明宿主安装或运行安全。Installation Owner还要求由可信宿主适配器独立检查精确包Hash和运行时快照；目前没有真实文件安装/核验适配器，也没有已供给的正式包签名公钥与License信任材料。不得把合成证据或已登记Package升级表述为真实安装。

## 本项实施范围

按`CR-PLG-011`把本WBS收敛为冻结生命周期中缺失的内部停用Owner：

1. 增加明确的Installation停用命令，要求精确Installation ID、actor、trace和expected lock_version。
2. 只允许当前可用且最新RuntimeValidation为COMPATIBLE的非RETIRED Installation；陈旧版本、缺失事实、状态不一致和越权写入均失败关闭。
3. 在同一plugin级锁及单一事务中删除全部当前启用操作、为每项追加DISABLED History与对应Audit，将Installation置为DISABLED并递增lock_version。Audit失败时整体回滚。
4. 已DISABLED且无启用操作的匹配版本重放可作为无变更结果；已RETIRED、INCOMPATIBLE或不一致事实拒绝。
5. 不增加表/字段/API/外部依赖，不挂载HTTP/默认生产组合，不安装或执行插件；Migration只有在当前数据库guard不支持现有冻结DISABLED事实时才允许由后续CR提出，实施前复核0227～0229 guard。

## 编码前检查与验收

- 冻结API：不改变路径、DTO、错误语义或版本；此项只补内部Owner能力。
- 持久化：复用`SqlAlchemyPluginActivationRepository.apply_activation`及History/Audit Port；由托管PG18验证零/多操作状态、安装状态和版本锁。
- 并发与回滚：覆盖启用/停用竞争、expected version陈旧、Audit/History故障原子回滚与幂等无变化重放。
- 安全：不读取或输出Package正文、Secret、路径、stdio、环境变量；不触发子进程。
- 执行环境：仅GitHub hosted runner的D盘临时工作区与隔离PG18；本机/C盘不运行项目程序或测试。
- 验收：定向Owner测试、后端完整测试与wheel；若确有数据库写入，补充空库及有数据Migration验证；随后执行项目既有 hosted PG/父包验收链。最高结论为`PASS_SCOPE_LIMITED`，不关闭Pilot/Gate/Release。

## 已登记差异与风险

原A06标题同时覆盖生命周期组合和真实宿主安装适配器，后者被当前正式签名信任材料缺失阻断。为持续完成不依赖该前置的冻结API生命周期核心，本WBS先处理可独立验收的人工停用Owner；真实Package安装、文件ACL/原子部署、Windows 11实机与正式信任源作为独立后续任务保留。该拆分不放宽安全条件、不伪造安装事实，也不更改冻结模型或API。
