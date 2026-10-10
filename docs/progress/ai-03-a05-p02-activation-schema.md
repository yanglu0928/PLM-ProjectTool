# AI-03-A05-P02：PromptVersion 激活首次结果 ORM/Migration

版本：0.1.0；日期：2026-10-02；状态：Windows 11 隔离 PG18 Schema 验证 PASS；内部激活命令/HTTP/生产迁移未实现。

依据：CR-AI-008、DEC-685、冻结 Prompt 模型。新增 AI 自有 ORM 与 Migration 0061，详见 [Schema 增量](../database-schema/ai-prompt-activation-result-0061-increment.md)。冻结提交/旧迁移不追写，通用收据、API 合同与权限未改。测试迁移头和 ORM 表清单同步扩展；首轮后端全量因这两处旧断言失败2项，更新为0061后定向7项和全量重跑通过，并保留失败记录。

Changed/Files：Prompt ORM、Alembic0061、迁移头/ORM 单测、隔离 PG18 验证、Schema/决策/CR/本进度/状态。Migration：0061 up/down；空库及有历史库升级、空表降级/重升、非空结果降级拒绝。API：无。兼容与回滚：新表与既有数据兼容；正式库升级尚未执行，有历史结果后必须前向修复或从受控备份恢复，不能自动 down。

Tests：Windows 11 隔离 PG18 脚本 exit0，验证 drift=0、复合 FK、状态/版本形态、Audit 唯一、UPDATE/DELETE/TRUNCATE 拒绝和 Prompt 旧历史保留；随机数据库已删除、临时 PG 集群已正常停止。后端定向7、全量2082项通过/3项既有跳过；开发 wheel 构建通过，SHA-256 `89b3dcf08cb29fcecd63e81a8089c8ca5453028f61f8fa55b6e2813dc278c516`。Golden Dataset 未运行：本项无模型推理。

Known Issues：Schema 不等于可用激活；正式目标账户/生产迁移、实际权限/License/并发/Audit/收据同事务与 HTTP、Server2025/Debian13、Gate3/UAT/可用包未验。Next：`AI-03-A05-P03` 内部激活服务及隔离 PG18 权限/重放/回滚验证。
