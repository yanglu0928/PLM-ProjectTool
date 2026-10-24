# 测试与完成标准

## 每项功能的最低测试

所有功能至少具备 Unit、API、Permission、Exception 测试；复杂模块增加 Integration；AI 模块增加 Golden Dataset Regression。

核心 Domain 规则目标覆盖率不低于 80%；权限、Review、Stage Gate、License 不低于 90%。覆盖率不替代行为验收。

## 必测行为

- API：happy path、validation、duplicate、lock、project isolation、expired license。
- 集成：OCR→RAG、RAG→DeepSeek、Requirement→Prototype、Requirement→Solution、Solution→WBS、Solution→Plugin。
- 异常：AI/Reranker 不可用、DB 断开、文件损坏、Plugin crash、License 过期、磁盘不足。
- 权限：建立 Role × API × Project 矩阵；跨项目访问零容忍。
- 功能：至少跑通创建项目→交接→调研→需求→原型→方案→计划的完整 UAT 场景。

## 性能初始目标

- 20 并发。
- 非 AI GET P95 ≤ 500 ms。
- 普通写接口 P95 ≤ 1 s。
- 长 AI 任务提交 ≤ 1 s 返回 JobId。

这些指标仍须在实际 PoC/评审中确认，不得把未执行结果报告为 PASS。

## Definition of Done

Task 只有同时满足以下条件才可标记 Done：

```text
代码完成
+ 测试通过
+ Migration 通过（如适用）
+ API 文档更新（如适用）
+ 架构文档更新（如适用）
+ 无 P0/P1 blocker
+ 验收标准通过
```

否则状态必须为 Incomplete。

## 任务结果报告

明确列出：Changed、Files、Migration、API、Tests、Result（PASS/FAIL）、Known Issues、Next。未运行的测试必须明确写“未运行”，不得用代码审阅代替执行结果。

