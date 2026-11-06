# CR-EXEC-036：SUR-07-A08 initdb loader 只读隔离探针

日期：2026-11-07  
状态：实施前记录；A08 未通过。

## 证据

Hosted run [42272810533](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42272810533) 的A08已通过同run候选身份、stage完整性提取、D盘路径、PLM_P51 temp root和Harness语法检查。后续 packaged platform-write target layout中的 initdb.exe 子进程返回3221225781，即0xC0000135（Windows STATUS_DLL_NOT_FOUND）；安全调用帧定位至 verify.py → smoke_current_app_packaged_https.py → smoke_packaged_platform_write_https.py → smoke_packaged_pg18_migration.py:_run。PostgreSQL尚未启动，A08/Edge业务验证未开始。

同run A17使用其同源候选成功；现有证据不能说明是候选缺依赖、A08运行环境差异或仅target layout导致加载失败。原始stdout/stderr未输出，符合保密边界。

## 单点探针

在A08已经完整哈希/清单校验提取的stage中，以绝对路径执行 payload/pgsql/bin/initdb.exe --version。捕获stdout/stderr但立即丢弃，只留整数return code及固定Stage枚举。探针不建库、不写客户数据、不更改stage，并在initdb装载成功后继续原有 smoke。

若预探针同样返回0xC0000135，根因落在stage候选/loader环境，接着仅对照有限DLL存在性与A17运行环境；若预探针成功而installed target initdb失败，根因落在target layout/工作目录或进程环境，再针对该差异提出单一修复。任何情况均不跳过PG/Edge验收。

## 验收和回滚

GitHub Hosted Windows Server 2025 D盘完整流程；只用合成数据；仅输出探针return code、固定stage及既有安全字段。回滚只删除该 --version 探针。保留原A08 marker门槛、合成License和临时根清理；不在本机/C盘运行项目代码。
