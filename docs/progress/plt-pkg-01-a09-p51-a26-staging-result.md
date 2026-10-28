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
