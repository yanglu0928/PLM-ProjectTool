
## 1. 目标

从现在开始，本项目采用：

**默认自主执行 + Gate确认 + 异常升级**

模式。

目标：

- 减少用户重复确认；

- 减少聊天Token消耗；

- 保持架构和业务基线受控；

- 提高连续开发效率。


---

# 2. 默认规则

除本规则明确规定必须人工确认的事项外：

> AI拥有当前已批准Scope内的自主执行权限。

AI不得因为普通实现细节反复询问用户：

- 是否继续；

- 是否创建文件；

- 是否执行测试；

- 是否进入下一WBS；

- 是否修改内部实现；

- 是否修复普通Bug。


满足前置条件后直接执行。

---

# 3. L1自主执行

以下事项AI直接决定并执行：

- 已批准WBS任务；

- 普通代码实现；

- DTO；

- Repository；

- Service；

- API内部实现；

- UI实现；

- 单元测试；

- API测试；

- Bug修复；

- 非Breaking重构；

- 普通Migration；

- 普通日志；

- 普通错误码；

- 测试数据；

- 文档更新；

- 已批准技术组件的配置；

- 当前Task必要的小范围代码调整。


无需用户确认。

---

# 4. L2自主决策并记录

以下事项无需即时确认，但必须写入：

`docs/decisions/decision-log.md`

包括：

- 内部类名；

- DTO拆分；

- Repository组织；

- 普通目录调整；

- UI组件选择；

- 非Breaking API内部实现；

- 普通索引；

- 普通数据库约束；

- 测试结构；

- 内部算法实现选择；

- 性能优化；

- 不改变架构的重构。


记录：

```
Decision ID
Date
WBS
Decision
Reason
Impact
Rollback
```

记录后继续执行。

---

# 5. L3必须人工确认

只有以下情况必须停止并请求用户确认：

1. PoC失败，需要替换已确认技术；

2. 修改已锁定业务规则；

3. 修改技术栈；

4. 修改总体架构；

5. Breaking API Change；

6. 核心数据模型重大调整；

7. 新增第一版Scope；

8. 删除已确认Scope；

9. 新增重要第三方依赖；

10. 引入新的商业授权组件；

11. 修改安全/License核心机制；

12. 原验收标准无法实现；

13. 出现不可逆数据变更；

14. 存在两个会长期影响系统的架构方案且无法依据现有基线决定。


触发后：

```
[USER DECISION REQUIRED]

WBS:
问题:
为什么阻塞:
影响:
方案A:
方案B:
建议:
不处理后果:
```

然后停止受影响Task。

不受影响的并行Task允许继续。

---

# 6. 禁止普通确认

禁止向用户询问：

> 是否继续？

> 是否开始下一步？

> 是否创建这个文件？

> 是否执行测试？

> 是否修复这个Bug？

> 是否进入下一个WBS？

这些全部默认：

**YES。**

---

# 7. 自动继续规则

一个WBS满足：

```
Implementation PASS
Tests PASS
No L3 Change
No Blocker
```

则：

```
AUTO-CONTINUE
```

直接进入下一WBS。

---

# 8. Gate确认

只在以下Gate请求正式确认：

### Gate 1

Phase 0全部PoC完成。

确认：

技术验证结果。

### Gate 2

Architecture + Data Model + API Contract冻结。

确认：

正式开发基线。

### Gate 3

Platform Core + AI/RAG完成。

确认：

平台底座。

### Gate 4

Handover + Survey + Requirement完成。

确认：

核心实施业务链。

### Gate 5

Prototype + Solution + Output + Plan完成。

确认：

完整业务能力。

### Gate 6

Integration + Installation + Upgrade + Regression完成。

确认：

Release Candidate。

### Gate 7

UAT完成。

确认：

正式Release。

除这些Gate和L3事件：

> 不请求用户确认。

---

# 9. 聊天最小输出规则

普通PASS任务只输出：

```
[WBS X.X] PASS

Changed:
Tests:
Migration:
API:
Architecture:
Risk:

Next:
```

控制在必要信息范围。

---

# 10. BLOCKED输出

只有失败/阻塞时输出详细分析：

```
[WBS X.X] BLOCKED

Failure:
Root Cause:
Impact:
Attempted:
Option A:
Option B:
Recommendation:

USER DECISION REQUIRED: YES/NO
```

---

# 11. 详细记录位置

详细执行信息写入仓库，不在聊天重复。

```
docs/progress/
docs/poc/
docs/test-reports/
docs/decisions/
docs/architecture/adr/
```

聊天只报告摘要。

---

# 12. STATUS.md

项目根目录必须维护：

`STATUS.md`

至少记录：

```
Current Phase
Current WBS
Current Status
Completed Phases
Completed WBS
Blockers
Pending User Decisions
Architecture Version
DB Schema Version
API Contract Version
Test Summary
Next WBS
```

每完成一个WBS立即更新。

---

# 13. 新Session恢复

任何新的AI Session开始时：

首先读取：

```
.ai/SKILL.md
STATUS.md
```

然后按STATUS定位当前任务。

只有当前Task需要时再读取：

- Architecture；

- ADR；

- Data Model；

- API Contract；

- 对应模块文档。


禁止每次重新加载整个项目全部文档。

---

# 14. Token控制

遵循：

**按需读取，而不是全量读取。**

禁止：

- 每轮重复实施方案全文；

- 每轮重复架构全文；

- 每轮重复已完成WBS；

- 每轮输出完整测试日志；

- 每轮解释已确认技术选型。


测试日志写文件。

聊天只输出：

```
Tests: 42/42 PASS
```

---

# 15. 上下文压缩

每个Phase结束：

生成：

```
docs/progress/phase-X-summary.md
```

内容只包含：

- 完成内容；

- 关键决策；

- Schema变化；

- API变化；

- 遗留问题；

- 下一阶段输入。


下一Phase优先读取Summary，不重新读取全部历史。

---

# 16. 错误自动修复

普通：

- syntax error；

- type error；

- test failure；

- lint；

- import；

- Migration错误；

- API测试错误；


AI必须自行：

```
发现
→ 分析
→ 修复
→ 重测
```

最多进行合理次数的修复循环。

只有：

- 无法修复；

- 需要L3决策；

- 会改变基线；


才找用户。

---

# 17. 用户默认授权

用户默认授权AI：

> 在已确认实施方案、技术基线、当前Phase和WBS范围内，自主创建、修改、删除开发文件，自主执行测试，自主修复普通问题，自主进入下一WBS。

但不得越过L3边界。

---

# 18. 最终原则

项目开发模式从：

**Task → 用户确认 → Task → 用户确认**

修改为：

**Gate → AI连续执行 → 异常才找用户 → Gate**

正常开发过程：

> AI执行。

重大决策：

> 用户决定。
