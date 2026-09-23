# PLM 项目 AI 执行入口

本文件是新 Session 的最小恢复入口，不替代正式基线或项目 Skill。

## 启动顺序

1. 读取根目录 `STATUS.md`，定位当前 Phase、WBS、阻塞项和下一任务。
2. 读取根目录 `AI自主执行与最小人工确认规则 V1.0.md`。
3. 读取 `skills/plm-project-development/SKILL.md`。
4. 只读取当前任务所需的 Skill 参考文件、ADR、数据模型、API Contract 或模块文档。
5. 基线变化、Gate 或 L3 事件才重新读取相应正式基线全文。

## 执行模式

- L1：在批准 Scope 内直接执行、测试、修复、记录并进入下一任务。
- L2：写入 `docs/decisions/decision-log.md` 后继续。
- L3：停止受影响任务，按规则输出 `USER DECISION REQUIRED`。
- 不询问普通的“是否继续、是否测试、是否创建文件、是否修复”。

## 周额度 Gate

- 自动执行开始、WBS 切换前和长任务结束后检查 Codex/GPT 周额度。
- 周额度剩余低于 20% 时，保存安全检查点、更新 `STATUS.md` 并停止新任务。
- 额度缺失时记录为 `UNKNOWN`，不得猜测；继续执行前向用户报告读取失败。
- 额度重置或购买必须逐次取得用户明确确认。

## GitHub

- 在当前批准 Scope 和正确的 `feature/*`、`poc/*`、`release/*` 或 `develop` 分支内，可自主 fetch、commit、push。
- 推送前检查远端和 Secret；禁止 force push、直接提交 `main`、覆盖未知远端修改或提交客户资料。
