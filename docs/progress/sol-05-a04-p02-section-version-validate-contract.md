# SOL-05-A04-P02：SectionVersion VALIDATE 命令与报告合同

日期：2026-10-12。结果：`SECTION_VERSION_VALIDATE_CONTRACT_PASS`；仅内部纯合同，不代表真实 VALIDATE Owner/HTTP 可用。

编码前检查：Phase 2；输入冻结 API-04 `SOL_SECTION_VERSION_VALIDATE`、DM-05、CR-SOL-003、A04-P01 前置核查及既有 SurveyVersion 同事务幂等/Audit 模式；前置满足。单一问题为定义固定版本验证的命令身份、首结果报告、审计原因与失败关闭规则。仅修改 Solution application 合同、单元测试、实施细化文档；不改 DB、冻结路径、角色、依赖或现有数据。风险为六类来源未全部有真实 Owner，却把默认空或异常映射为通过；DEC-1188 先记录。

新增 `ValidateSectionVersion`、固定版本快照、六维 `PASS/FAIL/UNAVAILABLE` 事实与不可伪造结论的报告构造器。请求指纹只绑定 Project/Section/Version，Key 由通用作用域按操作者/项目/操作摘要处理；Trace 或新 Key 不改变请求指纹。默认事实全部 `UNAVAILABLE`，`valid` 只看完整性/正文/需求/证据四维，`ready_for_review` 须再有 Trace/Spec 两维 PASS 且 DRAFT；非 DRAFT 生成专门问题码。报告绑定 Audit ID、Trace、固定指纹、计数与带时区观察时间，任何字段/结论不一致拒绝。六位 Audit reason 编码严格往返，供后续 Owner 从首次审计恢复报告，不能靠现时来源重算旧同号结果。

定向 26 项通过，覆盖有效/无效命令和 Key、原请求指纹、六维各 FAIL/UNAVAILABLE、缺证据默认不就绪、全部证明的规则正例、非 DRAFT、跨项目快照和伪造结论/问题码/时间拒绝、审计原因码往返与异常拒绝。最终后端全量 3573 通过/3 跳过/5583 子测试。初次 wheel CLI 尝试因当前 venv 无 `build`/`pip` 可执行模块而失败；随后直接调用项目配置的 setuptools build backend 成功生成 `py3-none-any` 开发 wheel，未将前两次工具调用误记为成功。无 Migration；未运行实际 VALIDATE API、PG、权限/License 或浏览器测试。

下一项 `SOL-05-A04-P03`：真实受权 Owner 在同事务锁定固定快照，证明当前 Document/Requirement/Evidence、Trace/Spec，追加 Audit 与持久收据；缺 Spec/Trace 时必须按未就绪报告返回，不得用合成全 PASS 对外宣称。随后再接冻结 HTTP/Windows 和 Edge/PG；Gate3/Pilot/Release 均未通过。TraceLink：Gate2 API-04/DM-05 → CR-SOL-003 → A04-P01/DEC-1188 → 本 P02 → P03/HTTP/Windows/UI → Review → Gate3/Pilot。
