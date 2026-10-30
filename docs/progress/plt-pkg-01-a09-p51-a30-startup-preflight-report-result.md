# PLT-PKG-01-A09-P51-A30：启动前置诊断报告结果

- 日期：2026-10-30
- 结果：PASS_LIMITED
- Hosted run：Windows Server 2025 run [40988858723](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40988858723)，PG smoke job成功；来源提交7eed6471492c71b60345b5a1311be483f90c5657。
- 执行位置：GitHub hosted runner D: RUNNER_TEMP；本机未运行项目代码。

## 变更

- 父包增加 payload/check-startup.ps1，只读取父包manifest的非秘密启动前置字段，输出status=BLOCKED、release_eligible=false、legal_clearance=false、blocker codes和固定英文解释，然后以exit 2返回；不会启动API/Caddy/PostgreSQL或打开监听。
- README-FIRST增加文档命令和结果解释。正向ready不可达，诊断不替代许可证/信任验证。
- 父包组装器检查诊断脚本无私钥/API Key/密码/PFX/P12标记；script随包hash清单纳管。

## 验收

- 同源父包候选：20,119项payload，archive SHA-256 2c9290295af9c86ea711cb59c93393daf4474ae0a57a7648f93d50abb0c395a1；parent artifact 12948044681，PG smoke evidence artifact 12948109610（截至2026-11-13保留）。
- actual candidate输出BLOCKED；含manifest声明的五种缺失前置阻断码，加NON_RELEASE_CANDIDATE；诊断messages 7条，不含运行路径/敏感标记，exit 2，stderr为空。
- 4类额外输入矩阵（伪造全ready且release/legal、附加字段、布尔字段错误类型、损坏JSON）均退出2、固定拒绝且不输出report。源manifest字节保持不变，诊断不启动listener；A29父包启动守门的7种篡改矩阵同轮继续通过。
- 父包PG 18.6/pgvector 0.8.6临时生命周期与D盘runner根清理成功；产品API未启动。该PG smoke job成功，A17 Edge job仍为并行验收，不纳入本项结果。

## 偏差与修正

- 首轮run 40985349086：诊断输出合同未满足，Harness未记录安全分类；失败发生于PG启动前。
- Run 40986507196：PowerShell诊断进程exit=1、stdout空；源码复核定位到TLS共用阻断码在hashtable重复定义。未启动服务。
- Run 40987631545：产品成功生成BLOCKED JSON；测试错误地要求证书/私钥拆分为两码，与manifest现有单一TLS阻断码不符。
- 上述偏差已事先记录于本任务precheck，并逐一最小修正；最终hosted smoke通过。无API/Schema/License机制变化。

## 限制

仅证明当前非发行候选诊断信息准确且在错误输入时失败关闭。正式公钥/License trust、服务身份/凭据/ACL/TLS、安装升级、Windows 11实机、用户验收和法律发行审核仍未完成。Pilot/Gate 3/正式Release保持NOT_READY。

## 追溯

- 编码前与偏差记录：docs/progress/plt-pkg-01-a09-p51-a30-startup-preflight-report-precheck.md
- CHANGELOG/STATUS同步于同分支后续提交。
