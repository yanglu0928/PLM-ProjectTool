# CR-EXEC-039：SUR-07-A08 PostgreSQL 临时环境 A/B

日期：2026-11-07  
状态：实施前记录；Hosted 复验中，A08 尚未通过。

## 证据与差异

Hosted run [42282788499](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42282788499) 中，目标布局 initdb.exe --version 与 postgres.exe --version 在实际 PG 子进程环境下均返回 0；随后完整 initdb 仍以 3221225781/0xC0000135 退出。源码对照发现 A08 platform-write smoke 为单个 PostgreSQL run 设置 TEMP/TMP 为其专属 pg_run，而既有 PG smoke 的通用环境并不覆盖这两个变量。此差异尚未证明为根因，产品未改。

## 实施前方案

在首次实际 initdb 前，于同一个 pg_run 直属创建全新 disposable probe 目录，复制原 initdb 参数，仅将 --pgdata 指向该探针数据目录；保持候选二进制、PATH、用户名、认证、编码、locale、工作目录不变，仅将 TEMP/TMP 改为本轮已校验的 D 盘 RUNNER_TEMP 专属 PLMToolTemp 根。stdout/stderr直连 DEVNULL，只保留数值退出码或固定 timeout/launch_error 分类。探针目录在受控父目录/前缀/D盘/ASCII所有权检查后清理。

仅当该真实 initdb 对照返回 0 时，才把相同 TEMP/TMP 变化应用于随后原有完整 smoke 的 initdb 子进程；否则保持原环境运行原 smoke 并记录结果。完整 smoke 验收内容及通过markers不变。此为一个限定假设的 A/B，不会推广到产品运行配置。

## 影响、风险、回滚

只改 A08 verifier 的进程包装、诊断字段和 workflow allowlist，不修改平台写 smoke 公共代码或产品环境变量默认值。探针会创建一个临时空 PostgreSQL cluster，不含业务数据，并在 D 盘 owned pg_run 中精确清理；异常时仍由父 A08 runRoot清理保护。若对照也失败，则不继续围绕 TEMP/TMP 试错，转向无依赖该初始化运行时差异的后续 WBS，并把 A08维持为阻塞/未通过。回滚仅删除探针及其诊断扩展即可。

## 验证

Hosted Windows Server 2025 同run候选、D盘owned根；完整工作流及 A08原始markers必须通过才可记 PASS_LIMITED。该托管证据不代表 Windows 11 实机、Pilot、Gate或正式Release。
