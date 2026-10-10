# AI-04-A04-P03：Egress Authorization / Revocation Schema0069

- 日期：2026-10-03
- 结果：PASS（Windows 11 / PostgreSQL 18.6 隔离验证）
- 依据：CR-AI-013、DEC-706～708、冻结 `EGRESS_AUTHORIZE/REVOKE`

Schema0069 新增 Authorization Root、不可变 Revocation 事件及 Authorize/Revoke 首次结果。Authorization 复制 Preview 的最小批准边界，只允许缩小数据类别、记录/字节/Token/重试上限和有效期，Provider/Config/Model/Region、Purpose、Payload/Source 指纹必须与不可变 Preview 一致。批准时 Provider 必须 ACTIVE、所选配置必须仍是当前版本、Model 必须 AVAILABLE。

Authorization 只能 `AUTHORIZED@0 → REVOKED@1`；批准与首次结果、撤销与事件/首次结果通过延迟约束触发器强制在同一事务成套落库。核心批准事实、撤销事件和首次结果不可改删/Truncate；空表可降0068，有历史时拒绝物理降级。

验证：Win11 隔离 PG18.6 空库 up/down/re-up、已有0068 Preview升级、Alembic drift=0、越界/过期/角色/缺结果授权、缺事件/缺结果撤销、单向状态、历史不可变和非空拒降均 PASS；后端2111运行/3跳过PASS。开发wheel SHA-256 `a9f4e426e9e132960da559d8e2a931493f6fb978742f234bde33304d99785700`。

首轮迁移在 PL/pgSQL 中使用了保留语义的变量名 `authorization`，首轮验证失败；更名为 `auth_row` 并全量重跑。验证脚本的合成撤销文本首轮少一个 SQL 引号，仅修正夹具后再次全量重跑，两次失败均未放宽生产约束。

边界：0069 仅是持久层；Project 当前成员角色、Session/CSRF/License、部署批准策略及原批准者身份由后续 Application Port 在同事务内重验。未开放 HTTP 或真实外发。
