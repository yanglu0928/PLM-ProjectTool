# PLT-PKG-01-A09-P16：统一+PG18候选只读安装门禁

日期：2026-10-01；状态：`READ_ONLY_GATE_PLAN_PASS / INSTALL_NOT_AUTHORIZED`。

编码前：Phase 2，输入为P15固定ZIP SHA-256 `c54a7862872d402a6c9763287a508dc63dd602049f93aa6097e5a8e8e0766ef2`、Gate 2冻结基线、ADR-013及Windows安装根/发行规则。前置P15完整性和隔离PG功能均通过，但法律、正式License、安装与服务账户未通过；因此本项仅只读计划。涉及模块为打包工具；实体/API/权限/Migration均无。验收：不安全安装路径必须先于ZIP I/O拒绝；固定ZIP整体/21,103件逐项哈希、七类运行/许可目录、manifest非发行与双来源声明通过；返回禁止安装并列开放门禁。风险是将规划误当现场许可，故字段显式禁止。

Windows11真实输入核查PASS：`C:\PLMTool`通过ASCII路径校验且当前不存在；固定ZIP来源分别为P10 `e4fdbcb601f526fd147b73b3e510e82653d85841503b5589dbf5c5d7c2f2eb50`与P12 `d0e038b43240369f7cd66396c34cd8e56d5a7a5a51ae3bc6f5fc41783baa7fd9`，21,103/21,103载荷Hash通过；manifest标识非发行、无安装/DB启动、法律与对应源码未清。定向单元2/2。实际 `archive_extracted=false`、`services_changed=false`、`migration_executed=false`、`install_authorized=false`。

下一项转向隔离安装装配：在非生产ASCII新目录检查运行目录映射、示例配置、可执行入口和启动命令能否组合，不触碰`C:\PLMTool`或SCM。正式产品License/签名、第三方NOTICE/对应源码与法律复核、目标服务账户/ACL/HTTPS、备份升级、质量/UAT、Windows Server 2025及暂缓的Debian13仍是客观发行门禁。回滚仅撤新只读工具/记录，无系统状态变化。
