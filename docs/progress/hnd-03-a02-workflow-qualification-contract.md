# HND-03-A02：Handover Workflow 资格领域合同

日期：2026-10-05。结论：`HND_03_A02_WORKFLOW_QUALIFICATION_CONTRACT_PASS`。下一项：`HND-03-A03` Handover 当前事实 Repository/Owner。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core，Gate 3保持BLOCKED
当前WBS：HND-03-A02
输入基线：冻结DM-02/DM-05、API-02、六阶段Workflow V1、HND-03-A01资格边界
前置任务：HND-03-A01 PASS；Handover Analysis/Review/Action运行链已存在
涉及模块：handover application；本项不让workflow直查业务表
涉及实体：HND-01/HND-02/HND-03当前观测、Evidence/ReviewRound最小资格输出
涉及API：无公开API、无冻结合同变更
涉及权限：无新角色；A03 Owner将在真实读取时重验项目授权
验收标准：纯策略固定两个Item、正式Version/Review、阻断Item、Action终态、Evidence当前观测和稳定指纹；正反例全覆盖
风险：值对象被跨项目手工组装、Evidence只绑UUID不绑当前版本、SUBMITTED/CANCELLED被当成闭环、策略误以为已有数据库事实
```

## 实施结果

- 新增无I/O的`HandoverWorkflowQualificationPolicy`及严格不可变值对象；只接受`HANDOVER_BASELINE`/`HANDOVER_ISSUES`，不访问数据库、不提交事务、不写Workflow Checklist。
- 正式基线必须为ACTIVE Analysis的精确当前APPROVED Version；Review必须为同Project/同Subject/同Version的`HND-02 + HANDOVER_ALL_V1 + APPROVED`，且Review fingerprint与Version fingerprint一致。
- 阻断规则固定为`source_missing=true`或`NEED_CONFIRM/CONFLICT/RISK`。每个阻断Item的所有未取消Action均必须为`VERIFIED/CLOSED`；只有CANCELLED、OPEN、IN_PROGRESS、SUBMITTED或已验证与未完成重复项并存均失败关闭。
- `VERIFIED/CLOSED`必须同时具有响应DocumentVersion、SUBMISSION Evidence和VERIFICATION Evidence；`CLOSED`还必须有Resolution Trace。
- 输出仅保留最小Evidence/Review观测，再次验证嵌套Project/Version一致性。资格SHA-256绑定Version/Review、Item/Action和Evidence的`lock_version + content_fingerprint`，避免只用UUID形成陈旧证明。

## 兼容、回滚与验证

这是模块内部非破坏性增量：无Schema/Migration、无公开API/权限/配置/依赖变更，无网络调用、Secret或客户数据外发。删除本策略文件及其后续注册即可回滚，不改写已有Handover/Workflow历史。

验证结果：

- 定向11/11 PASS：基线/问题正例、VERIFIED/CLOSED、只取消、未完成重复Action、保守阻断矩阵、Evidence缺失、Review/Version漂移、跨Project嵌套和Evidence指纹变化。
- Windows 11后端全量2725项运行、3项跳过、0失败。首次从仓库根运行`unittest discover -t .`因中文路径下start directory不可导入而未发现测试，改为在`apps/backend`内`discover -s tests`后完整通过；该调用偏差未当作产品PASS证据。
- 开发wheel构建通过，SHA-256 `8aec40adfd09200f8d06f171aa9d2c1f6e25f0dda62784f2962701bd6be1c2bd`；该wheel不是最终可交付发行包。

本结论只证明资格领域合同的确定性与失败关闭，不证明当前PostgreSQL事实、下游Owner调用、Workflow Checklist写入、Stage Transition、Gate 3或发行通过；这些从A03继续。
