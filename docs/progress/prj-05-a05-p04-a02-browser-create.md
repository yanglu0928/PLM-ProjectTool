# PRJ-05-A05-P04-A02 Windows11 真实浏览器创建项目

2026-09-28 / 0.1.0.dev0 / `WINDOWS11_SYNTHETIC_PASS`（创建浏览器行为与隔离PG终态；环境中断另记）。

编码前检查：Gate2已批准，前置P03页面合同/P04-A01真实HTTP与PG链通过；DEC-412先登记。只扩自有fixture`--create-browser`模式，不改生产实体/Schema/API/权限/依赖或Migration。唯一临时库、角色、Vault合成凭据及loopback Vite/Uvicorn，仅测试数据；回滚撤验证增量，无迁移。

浏览器观察：真实Codex IAB在`/login`登录合成部署管理员，创建页显示三个账户候选；选`Synthetic First Manager`启用账户，输入`CREATE-P04`/`Synthetic Created Project`并点击一次创建。页面出现“项目创建已确认”及新项目ID，且说明管理员不会自动成为项目成员。没有通过脚本直接代替UI提交。

数据库与清理：fixture收到浏览器核验信号后SQL精确断言3项目（预置2+新增1）、1会话、2有效成员、新项目首位负责人1、`PROJECT_CREATED`审计1、COMPLETED幂等收据1，进程exit0并报告库/角色不存在、Vault CredRead 1168。随后浏览器标签关闭调用被轮次中断，未再对标签输入；本机PG服务亦异常停止，启动时日志记录自动WAL恢复。恢复后外部只读查询`prj05a04%`库0/角色0，旧`--api-only`只读链另轮回归exit0且自清理。因浏览器关闭被中断，不声称标签已关闭；终态SQL/清理和本机服务异常分开报告。

限制：只证明Windows11本机合成License、loopback浏览器/PG路径；不证明正式公钥/可信时间、HTTPS、Server2025/Debian、CR-AUT-008性能、全部UAT或可用程序包。Gate3仍未通过；下一按WBS推进正式发行前置与其余平台/质量约束。
