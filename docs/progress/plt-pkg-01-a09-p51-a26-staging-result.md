# PLT-PKG-01-A09-P51-A26：候选暂存实施记录

- 日期：2026-10-28
- 状态：IMPLEMENTED_AWAITING_HOSTED_VALIDATION
- 编码前检查：docs/progress/plt-pkg-01-a09-p51-a26-staging-precheck.md
- 变更：新增stage_windows_parent_candidate_cloud.py，仅接受RUNNER_TEMP直接子目录的新目标；核对parent artifact summary、archive SHA-256、manifest非发行/未法务放行状态、来源/Workflow、完整payload checksum inventory、safe path与symlink防护；先提取至唯一同盘临时目录并逐项验证摘要，再同卷原子rename至目标；写入非敏感staging receipt。smoke增加成功暂存、拒绝runner temp以外目标的验证，并在临时空间核对嵌入式python存在后立即清理暂存产物。
- Secret/安装边界：不读凭据/密钥、不启服务/数据库、不触碰固定安装根/注册表/快捷方式；产物仍release_eligible=false/legal_clearance=false。
- 验证状态：尚未运行；只由GitHub hosted Windows workflow执行。首次失败/修复必须留记录。


## 首轮托管验证偏差

- Run 40623688321：基础CI、同提交组件和父包组装/readback成功；D盘staging在候选文件名安全检查时拒绝，错误仅报告存在被禁止扩展名。未生成staging目标；stage工具异常分支清理临时目录。A25/A24/PG后续烟测未执行，run不计通过。
- 下一轮诊断只输出被拦截扩展名，不打印完整归档路径或文件内容；据实际已固定组件清单判断是否应排除该类型，不能放松对密钥、凭据和日志的禁止。


## A26 被拒扩展名定位

- run 40624928787在安全文件名检查报告禁止扩展名 .pem。编码前复核既有嵌入式backend构建器：仓库明确只纳入精确路径 packages/certifi/cacert.pem，并核验至少包含证书块且不含 PRIVATE KEY；其他 PEM 和 .key/.pfx/.p12仍列入阻止列表。
- 下一步仅允许 staged archive 内确切路径 payload/runtime/packages/certifi/cacert.pem，并要求内容由一个或多个完整BEGIN/END CERTIFICATE PEM块组成、仅含Base64与空白、不含PRIVATE KEY标记；其余.pem一律拒绝。仍先以父包SHA-256清单校验该文件内容，不向包写入任何密钥。
- 此调整实施前记录；尚未通过hosted重验。


## 最终云端验收

- 最终修复后Run 40630592127全部7/7 jobs通过；该run head为192fc1737e50c6801e19ab386cc1e596986777d8。
- hosted Windows Server 2025 D盘Runner temp中，候选staging安全路径检查通过：越界目标拒绝、已有目录内容保留、唯一新目标原子暂存、20118项逐项SHA-256校验和本次目录清理。
- 公共CA bundle唯一路径白名单仍生效；标准文件/带ASCII注释的正例及私钥标记、未知文本、非法Base64、截断块负例全部通过。根因更正记录说明之前负例夹具用了字面反斜杠+n，后续已修正为LF并通过。
- Smoke回执artifact 12791816380（867 bytes）：候选摘要SHA-256 024a4e2582e06e6543781cf1f9b14b2f65269bf0b4315c8ecb4adc504f2e8751，PG18.6、pgvector0.8.6，Caddy2.11.4 loopback SPA/API代理；服务与数据库仅临时启动后清理。产品API未启动，License信任未用。
- 父包artifact 12791926409（14天保留），外层ZIP 372572693 bytes；候选本身20118 payload文件，内层ZIP SHA-256如上。run成功仅证明候选完整性和受控暂存，不代表Pilot、安装或Release。
- 结论：A26 PASS_LIMITED；两次失败及纠正均保留在相邻progress记录。Gate未变，Pilot和正式Release仍NOT_READY。
