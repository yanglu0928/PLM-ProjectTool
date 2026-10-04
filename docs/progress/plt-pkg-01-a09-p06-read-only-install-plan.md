# PLT-PKG-01-A09-P06：Windows统一候选只读安装计划

日期：2026-10-01；状态：`READ_ONLY_PLAN_INTERNAL_PASS / INSTALL_NOT_AUTHORIZED`。

## 编码前检查

- Phase/WBS：Phase 2 / 本项。输入基线：Gate2冻结、A09-P02候选ZIP及A09-P04安装根前置规则；A09-P05只读缺口矩阵。前置已满足。
- 涉及模块：`tools/plan_windows_unified_install.py`；实体/API/权限/Migration：无。正式服务注册器与数据库工具不调用。
- 验收：先拒绝不安全安装根，再校验固定ZIP SHA-256、成员安全/唯一、manifest非发行身份、106项Python/34项无JBIG声明、19,449件逐件Hash及清单一致；输出只读计划并固定`install_authorized=false`。不得解包、复制、注册SCM或迁移。
- 风险/回滚：固定当前候选SHA，换包须显式更新来源/测试/记录；工具只读，撤工具即可回滚，不触及系统安装或历史包。

本机真实候选 SHA-256 `da285e1c88d45f195d141f5eb6cba5f887f019063f4547a0a54ecae78c251bff`、安装根`C:\PLMTool`返回`NON_RELEASE_READ_ONLY_INSTALL_PLAN`，19,449件Hash均一致，106项Python、34项无JBIG PE；`install_authorized=false`、`release_eligible=false`。输出逐项列明正式License/信任源、NOTICE/源码、PostgreSQL18/pgvector、HTTPS/ACL/三服务、备份/静止及真实质量/Server2025/Gate的开放门禁。没有创建`C:\PLMTool`。

定向单元4/4通过：合成清单正例、载荷篡改与伪发行声明拒绝、未知ZIP身份拒绝、非ASCII根在读取ZIP之前拒绝。工具不提供跳过Hash或强制安装开关。它是安装决策的只读前置，不是安装器；同样不代表物理断网、真实目标账户/Server2025或发行合法性通过。

下一WBS `PLT-PKG-01-A09-P07` 可实现非发行候选的**隔离安全暂存演练**：仅在明确临时ASCII测试根、新空目录和逐件Hash后复制，不占用正式`C:\PLMTool`；正式现场安装须等上述门禁分别关闭。`release_eligible=false`。
