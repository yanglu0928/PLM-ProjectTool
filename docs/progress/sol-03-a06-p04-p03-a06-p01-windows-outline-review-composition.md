# SOL-03-A06-P04-P03-A06-P01：Windows受控启动组合接入Outline Review

日期：2026-10-24。状态：`PASS`（组合合同及回归；正式信任/服务启动仍待）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A06-P01` |
| 输入基线 | 冻结SOL-03/统一Review合同、现有Windows `--platform`只读和`--platform-write`受控模式、A05-P02-A03真实Edge/PG证据 |
| 前置任务 | Outline完整当前来源Owner、送审/统一Review显式分发及隔离PG/Edge闭合已验；Windows启动已有License Guard、Document/Evidence来源和本机Vault/游标来源 |
| 涉及模块/实体 | `production_login.py`显式组合及合同测试；不新建Domain/Schema |
| 涉及API | 既有Outline固定版本`:submit-review`只在写模式挂载；Review读/列表在只读和写模式登记SOL-03，终态命令只在写模式登记；不改冻结路径或字段 |
| 涉及权限 | 沿用正式Session/Project/License/Reviewer资格和完整现时来源；必须在已有信任材料缺失时启动失败关闭，不用合成Key代替 |
| 验收标准 | Read模式SOL-03已知评审可读取但无送审/决定；Write模式送审与终态路由、SOL-03 Owner精确注入；缺Owner/存储/许可等启动失败关闭；合同测试、全量后端回归和隔离PG验证通过 |
| 风险/回滚 | 正式公钥/服务账户目前未供给，不把合成装配称生产可用；撤组合仅关闭新入口，历史Review不得删除。测试需覆盖默认模式及缺信任源 |

选择复用既有`create_windows_outline_review_subject(terminal_context=True)`，一次构造并注入统一Review读/列表/命令组合器；写模式同时挂载现有Outline送审Router。不复制需求/章节/Trace来源图，不扩大对外API、角色或License权益。

## 实施与验收

- Windows受控组合在平台只读和写模式复用已有License Guard、Document/Evidence来源及`settings.data_root`构造一个正式SOL-03终态Owner，并注入Review GET/LIST；写模式将同一Owner注入Review命令且挂载冻结Outline版本送审Router。默认无平台模式仍不开放该主体。
- 合同测试验证读/列表/命令持有同一精确Owner、只读模式不挂载送审、写模式挂载冻结POST；Owner来源构造失败在发布路由前整体失败关闭并释放运行时。现有生产组合合同49项/2子例通过，后端全量`4066 passed, 3 skipped, 6114 subtests passed`。
- A05-P02-A03已经在Windows 11隔离PG/Edge使用相同显式Owner/Router证明完整真实HTTP业务链；本WBS不把该证据误称为正式公钥/服务账户下的生产启动。无Schema迁移或冻结API变化。

## 边界与后续

正式服务账户Vault来源、公钥/License签发与离线安装尚未供给；真实生产组合启动与恢复未验，Pilot/Gate 3仍未通过。下一片`SOL-03-A06-P04-P03-A06-P02`核查受控Windows组合的可重复启动/停机和真实信任前置，之后继续Windows 11安装/升级包。回滚只能撤新组合暴露或前向修复，已产生评审历史不得删除。
