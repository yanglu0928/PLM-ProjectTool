# WFL-02-A02-A08：六阶段重复编号修复

日期：2026-10-06
状态：`WFL_02_A02_A08_STAGE_NUMBERING_PASS`

## 范围

A07真实Edge视觉QA确认阶段列表同时显示浏览器有序列表标记与标题中的`stage.order`，形成
`1. 1. HANDOVER`。本项只修复这一个非阻断可用性问题，不改变工作流状态、排序、权限或写入行为。

## 实施

- 保留语义化`ol`及其浏览器自动序号。
- 阶段标题改为`STAGE_KEY · STATE`，不再重复输出`stage.order`。
- 增加六个初始阶段标题的精确回归断言，防止重复编号重新出现。

## 验证

- `ProjectWorkflowView.spec.ts`：`15`项通过。
- 前端全量：`78`个测试文件、`1395`项通过。
- TypeScript类型检查与Vite生产构建通过，构建`164`个模块。
- 主JS为`599.01 kB`（gzip `149.65 kB`），保留既有大于500 kB分块警告。

本项无后端、Schema、Migration、冻结API、权限、依赖、Secret或数据外发变化。Survey、
Requirement及后续阶段Owner，性能、正式信任、Gate 3、UAT和发行仍未因此通过。
