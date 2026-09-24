# LIC-01-A03：受控导入命令与初始安装记录

- 日期：2026-09-24；结果：PASS（内部命令）；依据：Gate 2、ADR-006、DM-02、API-02、CR-LIC-001、DEC-20260924-091。
- Changed：Auth 模块验证当前 Session Token、CSRF、未撤销/未超时、凭据版本和 DeploymentAdmin；License 模块从可信 Port 取本产品公钥引用并预检 Ed25519。成功只建立 IMPORTED 安装及不可变签名文档，随 Audit 同事务；失败签名只保存脱敏验证事件与 Audit，不保存正文。错误权限不写安装或签名文档。
- Files：`installation_import.py`、`installation_import_repository.py`、`license_import_access.py`、单元测试和 PostgreSQL 临时库验证脚本。Migration：无。API：无公开路由。Permission：Session+CSRF+DeploymentAdmin 同事务核对。
- Tests：Windows 11/Python 3.13 全部后端 155/155 PASS；PostgreSQL 18.6 临时库验证正确授权、错误 CSRF、非管理员、会话撤销、签名拒绝、安装/文档/Audit 与审计失败回滚 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：预检只证明签名，不是 License 综合验证或活动授权；导入后的完整机器/有效期/可信时间验证及激活/部署 ValidationState 投影仍需执行。生产本产品公钥配置、受控 HTTP Session/CSRF 接线尚未完成；不可开放 License API 或通过 Gate 3/UAT。
- Next：LIC-01-A04 受控激活与部署验证状态投影。
