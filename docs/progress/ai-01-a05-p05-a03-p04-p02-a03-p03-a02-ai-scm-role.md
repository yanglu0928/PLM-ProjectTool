# AI-01-A05-P05-A03-P04-P02-A03-P03-A02：AI Provider Worker Windows 服务角色

日期：2026-10-02；状态：限定范围 PASS；依据 CR-AI-003、ADR-013、DEC-663。冻结 Gate 2 原始提交 `64cdf09` 不改写。

本 WBS 为 Provider Test 新增独立固定 SCM 角色 `AI_PROVIDER_WORKER` / `PLMProjectToolAIProviderWorker`，关联独立进程标记和宿主。宿主只有在数据库就绪且维护准入可用后报告 RUNNING；STOP 协作通知循环，待当前探针完成、取得静止证明、释放数据库后再移除标记。无有效受控策略时服务计划仅含原三角色，AI 安装及配置对账拒绝；只读盘点仍能发现第四服务是否被安装。原三角色命令不变。

验证：Windows11 定向模拟覆盖四角色唯一性、策略缺失/错误、AI 安装与对账拒绝及成功形状、运行标记、STOP 排空前不得释放资源；后端全量2032运行/3跳过。原生 SCM 只读盘点显示四服务均未安装，未作 SCM 写入或真实服务启动。开发 wheel SHA-256 `daf5c7ceae5e3925d4986bf0ef0e9440732e6e2576aa8599975373c67fd57aee`，仅开发产物，不具发行资格。

兼容与迁移：无 DB Schema、ORM/Migration、公开 `/api/v1`、依赖变化；旧 Bootstrap 无策略时不新增可安装命令，无数据迁移。未投产可撤本项第四角色增量；若投产，先受控停新任务并核对现有 Job/结果/Audit，保留历史后向前修复，不自动删除 SCM 服务。

剩余：A03 需在受控 Windows11 目标账户验证实际 SCM 安装/启动/停止、PID/账户/路径/标记和失联/长 I/O 静止；目标账户 Vault/License/ACL/CA 与 Server2025/Debian 也未验。真实厂商外发没有本项授权；Provider Test/Activate 公开生产路由、Gate3/UAT/正式可用程序包均未通过。
