# CR-SUR-003：PROJECT Review 多 Subject Owner 生产组合

日期：2026-10-06。状态：`IMPLEMENTED_VALIDATED_WINDOWS_11`。范围：`SUR-01-A04-A02-P04`。

## 偏差与原因

原P03计划为Survey建立单一Review生产组合，但现有Windows平台只能向FastAPI注入一个`review_command_router`，且当前组合把该Router固定绑定到Handover Owner。若再注入一份路径完全相同的Survey Router，请求会被先注册路由截获，未知Subject失败后不会继续尝试第二份Router，导致两业务不能同时工作。

## 调整方案

新增Review-owned `ProjectReviewSubjectRegistry`，以受控、唯一的`SUBJECT_TYPE`把create/start/transition/replay全套同事务回调分派到真实Owner；未知、重复或不完整Owner一律失败关闭。Windows生产组合仍只创建一个冻结Review Router，但注册Handover `HND-02`与Survey `SRV-02`两个Owner。默认、login-only和只读模式继续不挂载四写路径。

## 影响、迁移与回滚

- 不修改冻结URL、DTO、错误码、角色、License、Review事务内核或业务Owner语义；不增加Schema、Migration、依赖、Secret、网络和外发。
- 风险是错误分派造成跨Owner访问；以Subject类型白名单、重复拒绝、所有回调统一分派、未知类型负例和真实双Owner回归控制。
- 应用回滚可恢复原Handover单Owner组合，Survey Review HTTP随之关闭；数据库历史不删除、不降级。不存在数据迁移。

## 验证计划

Registry单元验证双Owner全方法分派、未知类型与重复注册失败关闭；生产组合单元验证仍只有冻结四路径；Windows 11/PostgreSQL 18.6以真实Session/Project/Review/Survey来源完成create/start/approve、升版、create/start/withdraw和幂等重放，并回归Handover组合合同、后端全量与wheel内容。Windows Server 2025和Debian 13不在本WBS实机验证。

## 实施与证据

已按方案实现唯一PROJECT Review Registry/Router并替换Windows平台写组合中的Handover单Owner工厂。Survey与Handover均通过Windows 11/PostgreSQL 18.6真实HTTP链；Registry/组合新增6项，后端2816项通过/3项跳过，wheel 1040项且SHA-256为`9334cdad39de0438c6fef6b9d40056c0ebe3b9bfc19c2fbad725fa8a0c2f825d`。无数据迁移，原Handover行为保持兼容。
