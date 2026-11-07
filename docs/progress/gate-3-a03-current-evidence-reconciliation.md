# GATE-3-A03：当前 Gate 3 与 Windows 11 Pilot 证据重排

- 日期：2026-11-07
- 结论：GATE_3_BLOCKED；Pilot 仍 NOT_READY。本项只核对当前可追溯证据和可执行性，不运行产品、不生成业务事实，也不改变冻结验收门槛。
- 输入：GATE-3-A01/A02、CR-EXEC-002、CR-PRT-006、CR-EXEC-039、P51-A36～A50、STATUS、run 42374803790。

## 当前证据

| 责任域 | 最新证据 | 判定 |
|---|---|---|
| 纵向业务链/输出读取 | 同轮父包 PG18 生命周期与 P40 live Edge：OutputArtifact 引用和 Document 内容流可按项目授权完成限定合成下载；真实 Output Create 因没有正式可信 Publisher 仍失败关闭。 | 读链存在有限 Hosted 证据；生产生成链未开放。 |
| 插件执行与持久状态 | PLG-03-A05～A08 各自有 Hosted PG18 受限通过记录；本轮 A06/A07/A08 专项成功。SurveyVersion packaged flow 单独受 initdb 0xC0000135 阻断，不能与 PluginExecution 专项混淆。 | 机制证据有限；真实信任、Worker/安装边界和整体运行链未关闭。 |
| 性能 | PRT 主机资源观察器独立 Hosted Windows 2025 测试及原生计数器读取通过；完整 Prototype 20 并发验证器在 initdb 数据目录阶段以 DATA_DIRECTORY_ACCESS_DENIED 停止，没有产生 P95。 | Gate 500ms 仍 FAIL；完整负载没有新测量。遵 CR-PRT-006 停止该单独初始化路径。 |
| 质量与 AI/RAG | 既有 GATE-3-A01 留存的历史分类/精确引用指标为 48%/74%；本次无新独立留出集或人工标签证据。 | 不得推定质量门槛通过；新的业务数据发送仍须按授权边界单独处理。 |
| 正式信任与部署 | P51-A36/A38 的 readiness 证据显示正式公钥/License trust、目标 DB credential reference、服务身份/ACL、TLS 证书/私钥及信任链均未核验，启动器保持 fail-closed。 | Pilot/正式部署仍被真实外部前置阻断，不能用合成值代替。 |
| 环境 | 本轮 22 个 Hosted jobs 中 20 个 success、2 个 failure（PRT、SUR-07-A08）；Windows Server 2025 runner D 盘仅是当前限定 CI 证据。 | 不推定 Windows 11 新设备、正式 Server 2025 部署、Debian 13、Pilot 或发行通过。 |

## 当前决策

1. 不以 PRT 观测器单测代替完整负载；不放宽 500ms 门槛、不调整连接池、不改产品目录/服务 ACL，也不重复 TEMP/PATH 探针。
2. 不重新开启 PRT 当前 initdb 路径。未来若有不同、可复用已成功父包 PG 生命周期的独立验收设计，必须另立 WBS 并先记录，不在本次失败任务内迭代。
3. 当前 Pilot 关键路径的下一实质性输入是受控安装/启动环境中的正式信任材料：发布公钥与真实签发/许可来源、服务运行身份及其数据/日志 ACL、目标 DB 凭据引用和真实 TLS 主机名/证书链。值和私钥不得进入 GitHub、聊天或日志；只需由用户在受控 Windows 11 环境配置，后续我们验证固定非秘密状态与结果。
4. 在上述材料未可用前，保持程序候选为非发行、不可启动；Gate 3/Pilot/正式 Release 不得改为 PASS。只要无其他已计划且不依赖这些材料的编码 WBS，不捏造新功能来制造进度。

## 后续

- 待正式信任前置在受控 Windows 11 环境配置后，按 CR-EXEC-002 继续真实装配/离线安装与受限内部试用验证；期间自动执行仍在 GitHub Hosted D 盘完成，除非明确进入受控本机试用。
- 当前尚不要求用户提供或发送私钥、密码、客户数据、证书私钥或 License 秘密。所需是受控环境中真实配置这些材料，并通过只读就绪报告给出脱敏结果。
- TraceLink：Gate 2 → CR-EXEC-002 → P51-A36～A50 → CR-PRT-006/Hosted run 42374803790 → 本 GATE-3-A03 → 受控 trust setup → Pilot。
