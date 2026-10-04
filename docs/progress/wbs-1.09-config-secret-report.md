# WBS 1.09 Config/Secret 基础边界验收记录

- 日期：2026-09-24
- 阶段：Phase 1 架构冻结与基础工程
- 状态：PASS（基础边界；不代表生产 Secret Store 已可用）
- 前置：WBS 1.02、1.04～1.08 PASS；Gate 2 冻结架构、数据模型、Schema 与 API Contract 未修改。
- 追溯：WBS 1.09 → AF-03 三层配置/Secret 分离、DM-02 SecretRecord 与 API-02 PLT-01/PLT-02 → `DEC-20260924-068` → Bootstrap/Secret Port 与示例模板 → Unit/Permission 回归与 wheel 验证。

## 交付与验证

新增非敏感 Bootstrap 配置加载器：只接受受限的 UTF-8 YAML、`PLM_` 环境覆盖，以及明确指定的开发 `.env`。YAML 安全加载、重复键、未知字段、危险 tag、超限文件、端口与绝对路径校验均失败关闭；错误只给固定信息，不回显配置原值或文件路径。配置模板不包含密钥。直接依赖固定为 [pydantic-settings 2.15.0](https://pypi.org/project/pydantic-settings/2.15.0/) 与 [PyYAML 6.0.3](https://pypi.org/project/PyYAML/6.0.3/)。

新增 `SecretRef`、受控 Purpose/Consumer、加密记录、密文读取/解密/Audit Port 与单次 `SecretResolver.use()` 契约：用途、消费方、ACTIVE、版本与密文元数据不符时不解密；访问失败或 Audit 失败统一脱敏并失败关闭。测试用可变缓冲区在作用域结束时清零，密文和主材料引用不进入对象 `repr`。这里的 Decryptor 仅为 Port，尚无真实加密算法、主密钥或持久化实现；测试中只有合成数据。

Windows 11 / Python 3.13.15 全量后端测试 72/72 PASS；安全负例覆盖 YAML、环境、开发 `.env`、Secret 消费方/状态/用途/密文/Audit/解密失败。backend wheel 构建 PASS，两个新模块和两项依赖均在包清单/元数据中。公开业务 API、正式业务表、Migration、真实密钥与客户数据外发均为 0。

## 兼容性、升级与剩余风险

当前版本仍为 `0.1.0.dev0` 未发行基础工程；安装 backend 时需安装上述新增依赖，无数据库升级。Windows Server 2025 与 Debian 13 未在本任务验证。

正式 PLT-01 SystemConfiguration 和 PLT-02 SecretRecord 仍需分别按冻结 Schema/API 交付 ORM、Migration、版本化命令、DeploymentAdmin 权限与 Audit。加密算法、数据库密文仓库、外部 `SecretKeyProvider` 的 Windows/Linux 保护、主材料独立备份/恢复及真实 Provider 调用尚未实现；在这些验证通过前，不能宣称生产 Secret 可用。Python 内存清零是尽力缩短作用域，不能保证清除第三方库复制的明文。下一任务为 `PLT-01-A01 SystemConfiguration ORM/Migration`，先建设非敏感版本化配置持久层。
