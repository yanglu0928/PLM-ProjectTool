# SUR-01-A03-P02-A03：DRAFT SurveyVersion 原子创建

日期：2026-10-06

状态：`SUR_01_A03_P02_A03_VERSION_CREATE_PASS`

已实现冻结双角色的完整定义版本创建：服务端规范化 Question/Option/Source/TargetDepartment 并计算指纹，消费 Handover、Capability、TEMPLATE Document 和 Project Department Owner 证明，在同一事务更新 Root 版本、写六表、Audit 与持久幂等收据。版本不可变并形成 supersede 链；本项不开放 HTTP、不导入客户事实。

实现中补足两项兼容边界：Document Owner 新增只返回固定 TEMPLATE 身份/哈希的最小证明，允许已受权 Survey 写使用 GLOBAL 或同项目模板而不暴露正文；Migration 0104 开放唯一合法的 Root `lock_version + 1` Owner 更新。Python `None` 对 JSONB 改为省略列，确保写入 SQL `NULL`。

验证：定向16项；Windows 11/PostgreSQL 18.6 四类来源、三代版本、重放/冲突、Audit 回滚、六表原子性、0104 空历史升降及历史拒降通过；后端2790项通过/3项跳过；wheel 1031项，SHA-256 `10391ff37ca46591eb3f098872add4df5088ee75edaa785ebf5905226b7ff05c`。

下一项：`SUR-01-A03-P03` SurveyVersion Validate Owner，验证条件引用/循环、题型规则、来源当前性和完整报告。
