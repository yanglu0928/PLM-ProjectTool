# CAP-01-A05-A07：Capability Windows 生产组合

日期：2026-10-05。结论：`CAP_01_A05_A07_WINDOWS_COMPOSITION_PASS`（隔离合成密钥）；正式目标账户密钥仪式仍为 Release 前置。下一项：`HND-01-A01` Handover 运行时前置核查。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A05-A07
输入基线：冻结API-01/API-04、DM-05、Schema0095、DEC-840～845
前置任务：十二个Operation的Owner、命令/送审/读取Router均已通过
涉及模块：capability/review/windows production composition/Vault
涉及实体：CapabilityBaseline、BaselineVersion、CapabilityItem、GLOBAL Review
涉及API：十二个冻结Capability Operation
涉及权限：DeploymentAdmin写与历史读；当前项目成员仅读当前APPROVED投影
验收标准：显式生产组合、缺密钥失败关闭、真实HTTP/PG、重放/状态边界、wheel
风险：正式密钥无恢复备份；GLOBAL Review时钟先于Subject校验；只读模式误挂写接口
```

## 实施结果

- 新增 Windows Capability 组合根。`--platform` 只挂五个读取 Operation，`--platform-write` 挂载全部十二个冻结 Operation；登录专用模式和普通默认应用保持不挂载。
- 两类分页分别读取 `capability-baseline-cursor-v1` 与 `capability-child-cursor-v1`；缺失、无效或非法组合模式统一拒绝启动，不回退到共享/硬编码密钥。
- 生产组合只使用既有 Owner、Repository、Session、Origin、License、Audit 与 GLOBAL Review 内核，没有跨模块直写或新增公开合同。
- 真实组合验证发现 GLOBAL Review 在 Subject 实时校验前采样开始时间，生产时钟会稳定早于 `verified_at` 并返回503；已改为在 Subject prepare/active-lock 后采样，并补充顺序回归测试。
- 当前账户没有两把正式 Capability 密钥。依据 `CR-CAP-004`，本项只用隔离合成 Resolver 验证机制；没有生成不可恢复正式 Secret，也没有把测试密钥写入仓库。

## 验证与证据

- Windows 组合/Review时序/生产入口定向42项通过。
- Windows 11/PostgreSQL 18.6 临时库真实迁移及 HTTP 覆盖 Baseline Create/List/Get/Patch/Archive、Version Create/List/Get/Items/Validate/Restrict/Submit Review 共十二个 Operation；验证首次送审重放、1个IN_REVIEW、1个RESTRICTED、1个ACTIVE与1个ARCHIVED Baseline、唯一GLOBAL Review，迁移 drift 为零，临时库已删除。
- 后端全量2597项通过，3项按既定环境条件跳过；`compileall`与`git diff --check`通过。
- 最终开发wheel内Capability/Review定向59项、解包Migration 4项通过；wheel SHA-256 `793500a98946317b3ba4c95e0909029b085814fe00cda5b9e17aaa2c17f87ea0`。

## 兼容、回滚与未关闭项

无Schema/Migration、公开API、生产依赖或客户数据外发变化。可停止注入三个 Capability Router 回滚新流量，合法历史保留。Review时钟修复只收紧真实时间顺序，不改变冻结状态机。

正式目标服务账户两把密钥的加密备份/ACL/恢复演练、正式License信任、性能、Windows Server 2025与Debian 13发行验证仍未关闭；本项不宣称生产或Gate 3通过。
