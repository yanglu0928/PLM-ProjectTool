# EVD-05-A02-P02：GLOBAL Evidence 创建包内拒绝矩阵

日期：2026-10-24；状态：`SYNTHETIC_DENIAL_MATRIX_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|当前 Phase/WBS|Phase 2 / `EVD-05-A02-P02`，只验证包内 GLOBAL Evidence 创建拒绝。|
|输入基线|冻结 `/api/v1`、`CR-EXEC-002`、`EVD-05-A02-P01` 正向 PASS；固定非发行候选 SHA `5b8e38f4f8e5440c74e7e0ecace43e435b4464ab5a8ae37e4010ecfdce4f1327`。|
|前置任务|P01 同源固定文档、CANDIDATE、Audit/收据、Edge/PG 验收已通过。|
|涉及模块/实体/API|仅增加验收脚本；Evidence、DocumentVersion、LicenseValidationState/Event、Session；`POST /api/v1/global/evidence`。不改产品 ORM、Migration、API。|
|涉及权限|匿名无 Session、普通用户无 GLOBAL 管理员权、管理员错误版本、模拟 EXPIRED 许可状态。|
|验收标准|各请求按契约拒绝；Evidence、`EVIDENCE_CREATED` Audit、`V1_EVIDENCE_CREATE` 收据计数不增加；同包 SHA 和临时资源清理。|
|风险|许可负例用隔离 PG 中追加合成 `EXPIRED` 验证事件与推进受保护单例状态，验证运行时失败关闭；不是自然到期或真实发行信任。P01 正向前置链会重跑，耗时较长。|

首次夹具启动使用不符合安装演练命名约束的 Temp 子目录，在任何解包或服务启动前被拒绝；已改为规定的 `plm-install-rehearsal-*` 名称后重跑。此失败不计为产品行为结论。

重跑同一候选 SHA 后，包内 Workflow HTTPS、GLOBAL 固定文档/基线 Edge 与 GLOBAL 整文档 Evidence Edge/PG 正向前置均通过。其后经包内 HTTPS 实测：匿名 401 `AUTH_SESSION_EXPIRED`、普通用户 404 `RESOURCE_NOT_FOUND`、管理员错误 DocumentVersion 404 `RESOURCE_NOT_FOUND`、合成 EXPIRED 验证状态 403 `LICENSE_OPERATION_DENIED`。在隔离 PG 中，正向单条 Evidence、`EVIDENCE_CREATED` Audit 和 `V1_EVIDENCE_CREATE` 收据计数始终维持 `(1,1,1)`；没有额外业务事实。EXPIRED 状态由新不可变验证事件和受保护单例版本递增形成，验收的是已失效状态下的运行时失败关闭，非自然时间到期。

验收器退出 0；22,194 件隔离布局核对，`fixed_candidate_unmodified=true`、候选原 SHA 不变，48 个合成 Vault 目标、包内 Python/Caddy/临时 PG 进程和临时文件均清理。代码只增加验收脚本，无产品 Migration/API 变化。`EVD-05-A02` 的此四项拒绝切片可关闭；后续若需真实自然到期/撤销场景，另立验收，不能由本次模拟推定。正式信任、法律放行、安装/UAT/Gate/Pilot/三平台发行均未通过。
