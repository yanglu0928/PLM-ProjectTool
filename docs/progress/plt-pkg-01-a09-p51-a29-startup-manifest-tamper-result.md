# PLT-PKG-01-A09-P51-A29：启动清单篡改抗性守门结果

- 日期：2026-10-30
- 结果：PASS_LIMITED（仅启动信任缺失时的拒绝边界）
- Hosted run：Windows Server 2025 run [40983612763](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40983612763)，job “Clean extraction and temporary PostgreSQL lifecycle smoke” 成功；同轮该项前置依赖均成功。完整并行A17 Edge job当时仍在收尾，未以其代替A29证据。
- 源提交：b7646312ca21e31c3c2853dfc57d78838a792b9a
- 执行位置：GitHub hosted runner D: RUNNER_TEMP；本机未运行项目代码。

## 变更

- start_windows_trial_candidate.ps1 对release/legal标记和所有ready状态采用严格JSON布尔类型检查；数据库凭据目标必须为预期字符串，阻断码必须是数组且为空；解析失败和任何不匹配均输出同一固定拒绝文本并退出1。
- smoke_windows_parent_package_pg_cloud.py 增加7种包内启动manifest篡改矩阵：全ready伪造、凭据目标路径篡改、布尔改字符串、阻断码改字符串、缺失阻断码、startup对象改字符串、JSON损坏。
- 不读取Credential Manager秘密blob，不提供正向生产启动，不涉及冻结API、业务Schema、Migration、权限或AI接线。

## 验收证据

- hosted D盘父包PG smoke job为success；7/7篡改用例返回固定拒绝，stdout为空，报告listener_started=false；源包manifest原始字节不变。
- 同一smoke：父包20,118个payload文件；archive SHA-256 070a162db0dcfb06c03f5608340491d7d54ab9089fc3f9942861558e7243eede；PG 18.6/pgvector 0.8.6临时生命周期及清理成功。
- 当前真实manifest的正式产品公钥、正式License信任、数据库凭据引用、服务身份ACL、TLS证书/私钥状态均明确false；生产入口缺目标数据库Credential时拒绝，启动协调器缺正式信任时拒绝。

## 限制

此项不证明正向生产启动、Windows 11设备运行、正式License/账户/TLS信任、安装升级、Pilot、Gate或Release通过。PASS_LIMITED只适用于当前非发行候选的守门行为。完整A17包内业务验收另见A28结果及run 40983612763的并行job。

## 追溯

- 编码前检查：docs/progress/plt-pkg-01-a09-p51-a29-startup-manifest-tamper-precheck.md
- 父包候选artifact：12946396716；PG smoke证据artifact：12946108453（截至2026-11-13）。
