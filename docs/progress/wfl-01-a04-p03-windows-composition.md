# WFL-01-A04-P03 Windows Workflow GET 组合

日期：2026-09-26；版本：0.1.0.dev0；结果：WINDOWS_SYNTHETIC_COMPOSITION_PASS。

## 编码前检查

Phase 2 Platform Core；前置 A04-P01 内部读取、A04-P02 可选 HTTP 已验证。输入为冻结 WORKFLOW_GET、CR-WFL-001/002 固定定义与实例结构；本任务仅组合接线，不改变 Schema、授权或签名机制。涉及 WorkflowReadService、Project 当前身份事实、现有 Windows 组合；实体只读。四项目角色可读，部署管理员不得绕过项目成员资格。验收为两种显式平台模式可读，默认/仅登录及 Workflow 写路径保持关闭，许可拒绝/缺信任源失败关闭。

## 实施与证据

- `production_login.py` 在既有显式平台分支装配真实 Workflow Repository、Session、项目授权与 License Guard；两种平台模式复用此组合。
- `validation/wfl-01-a03-p05-authorized-initialize/verify.py` 在随机隔离 PostgreSQL 库使用真实 Session/成员事实，合成 License/密钥提供器，验证四角色 200/ETag、跨项目与非成员管理员 404、License 403、默认/登录和 start/transition 404，缺 License 或游标信任源拒绝创建应用，读前后实例/审计数量不变。脚本已运行 PASS，临时库和临时数据目录由脚本清理。
- Windows 11 / Python 3.13 后端 641 项无失败，2 项既有符号链接权限环境跳过；未测覆盖率或性能。
- 开发 wheel 构建 PASS，SHA-256：`324adf955edca8665b0ed03ea01510bd39a96d458d5d018a836d5ea3719cb9f5`。这不是正式可交付安装包。

## 兼容、升级与回滚

无 Migration/依赖/Breaking API/架构变化；沿用 0030 数据库及既有显式平台可信来源。升级无需新增密钥。回滚为撤销 Router 装配，保留实例/审计，不重置进度。

## 边界与下一项

真实发行公钥与目标账户信任源未供给，不能标生产 PASS。Server 2025 未运行、Debian 13 暂不验证；实际 Gate、阶段推进、历史和性能未验。下一项 WFL-02-A01：核查冻结 StageTransition/Gate 历史模型与前置，不以状态字段代替实际业务证明；Gate 3 仍未通过。
