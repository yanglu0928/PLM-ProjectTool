# AUT-03-A07-P01：可信 Origin 部署配置

- 日期：2026-09-25；结果：PASS（仅非敏感配置前置，AUT-03-A07 仍未通过）。
- 当前Phase：Phase 2 Platform Core。
- 当前WBS：AUT-03-A07-P01。
- 输入基线：Gate 2 冻结 API-02 登录 Host/Origin 校验、AUT-03-A01 精确来源策略及 CR-AUT-002 装配顺序。
- 前置任务：AUT-03-A01、1.09 PASS；CR-AUT-002 已记录安全装配前置。
- 涉及模块：Platform BootstrapSettings；涉及实体：无；涉及API：无新增/变更公开 API；涉及权限：不授予任何权限，默认登录路由保持关闭。
- 验收标准：YAML 显式配置、`PLM_TRUSTED_ORIGINS` JSON 数组覆盖、缺省空集合、非列表/空值/超长/超过 16 项失败关闭，错误不回显原值；现有后端测试通过。
- 风险：此配置只限定输入形状；最终 URL/Host/HTTPS 语义必须在登录生产装配时由 `LoginOriginPolicy` 校验，不能凭配置加载成功就开放路由。

Changed：新增 `trusted_origins` 非敏感部署配置，缺省为空；不提供通配来源。配置仍遵循现有 YAML/显式开发环境文件/`PLM_` 环境覆盖顺序。正式装配必须用 Auth 来源策略对该集合再次校验，并保持失败关闭。

Files：`bootstrap_config.py`、`test_bootstrap_config.py`、本进度及决策/版本/状态记录。Migration：无；升级无需数据操作。API：无公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 306/306 PASS；配置和来源策略定向 15/15 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：安全运行数据库凭据来源和生产端到端装配未实现；生产 License/Secret Key Provider 与公开路由仍有独立前置。当前默认登录 404，Gate 3/UAT 未通过。

Next：继续完成安全运行数据库凭据来源，并以真实 Project 授权摘要和可信 Origin 做 AUT-03-A07 生产装配与端到端验证。
