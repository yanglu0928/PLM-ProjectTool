# PLT-PKG-01-A09-P51-A26：首次暂存验收失败记录

- 日期：2026-10-28
- 托管验证：GitHub Actions run 40626979502，PR #56，Windows Server 2025 hosted runner
- 覆盖结果：后端测试/wheel、前端测试与构建、Python 3.13.15运行时、PG18/pgvector组件、embedded backend、父包组装均成功；最终D盘smoke失败，A26不得判PASS。
- 失败步骤：`stage_candidate` 在检查唯一白名单 `payload/runtime/packages/certifi/cacert.pem` 时拒绝该文件，错误为“allowlisted certifi bundle is not public-certificate-only”。未进入成功暂存收据、既有PG18 smoke或最终清理验收。
- 风险边界：拒绝是失败关闭行为；本次工具未安装软件、启动服务或触及用户设备。父包为非发行候选；License/公钥、客户数据及私钥未被调用或外发。
- 根因判断：当前验证器只允许PEM证书块与Base64/空白字节，未允许标准公共CA bundle中可能存在的注释行。尚未从本次日志证明文件具体哪一行触发，因此修复按格式兼容来做，不放宽目标路径或密钥约束。
- 变更前计划：仅对精确certifi公共bundle路径允许空行、以“#”起始的ASCII注释行及完整PEM证书块；严格Base64解码每个证书主体；拒绝其余内容、任意密钥标记、截断块、空主体及任何其他.pem路径。逐项SHA-256校验保持不变。
- 验证计划：Hosted Windows D: Runner执行合法bundle正例、非法行/密钥/截断证书负例，以及越界目标拒绝、已有目录不覆盖、完整候选暂存/清理和原A24/A25/PG smoke回归；失败先记录后修复。
- 偏差/影响：仅修改候选输入安全格式检查；不改产品API、数据库、冻结基线、服务运行或安装布局。旧验证失败记录保留。
- 状态：`A26_FAIL_LIMITED_REMEDIATION_RECORDED`；Pilot与正式Release继续`NOT_READY`。

