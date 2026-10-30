# PLT-PKG-01-A09-P51-A36：Windows 11 Pilot 信任与安全运行前置可自动化性检查结果

- 日期：2026-10-30
- 状态：PASS_LIMITED（只读代码/配置盘点与合成单测；没有安装或启动产品）
- 前置检查：`plt-pkg-01-a09-p51-a36-windows11-trust-prerequisite-audit-precheck.md`
- 上一项：A35 `PASS_LIMITED`，Windows 11 Home build 26300，D盘隔离包替换/恢复。

## 结论

本轮没有可在缺少正式材料时安全关闭的生产启动前置。现有启动守门、缺项诊断和若干“材料到位后可自动验证”的基础已具备；但正式产品公钥/License、数据库凭据身份、服务账户与 ACL、真实 TLS 证书及其主机名/信任链/续期策略没有被本轮提供或验证。保持 Pilot `NOT_READY`、Gate 3 未通过、正式 Release `NOT_READY`。没有伪造信任材料或把 manifest 布尔值改为真。

| 前置项 | 已实现的自动检查 | 需真实输入后才能验证 | 本轮结论 |
|---|---|---|---|
| 产品 License 信任 | 父包启动器要求包内公钥资源，并要求独立的 formal trust 验证标志；缺项输出固定 `FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED` / `FORMAL_LICENSE_TRUST_NOT_VERIFIED` | 正式发布公钥、有效 License、MAC/时间信任来源及密钥/许可绑定证据 | 未关闭；仓库跟踪文件中不存在 `product_public_key.json`；未检查工作台私钥或 License 值 |
| 数据库凭据 | 当前账户 Credential Manager 中只检查固定目标 `PLMProjectTool/Database` 是否存在；若发现已有凭据则跳过连接探针，避免误连未限定数据库；不存在时只执行隔离的失败关闭检查 | 用户/服务账户目标凭据、数据库实例/数据库名/角色限定与 PG TLS/连接验证 | 未关闭；没有读取、记录或回显凭据值 |
| 服务身份与目录权限 | manifest 固定要求 `service_identity_acl_verified=true`；默认启动仍拒绝 | 选定服务账户、SCM 登录配置、安装/数据/日志目录 ACL、备份恢复身份与实际权限核验 | 未关闭；本轮未注册/修改服务、ACL 或安装目录 |
| HTTPS/TLS | manifest 固定要求证书/私钥配置标志；已有证书输入检查工具可在材料提供后验证部分有效期/主机名/密钥匹配 | 受控主机名、真实证书/私钥、CA 信任链、部署路径 ACL、续期与轮换策略 | 未关闭；没有测试/生成/读取真实证书或私钥 |

## 验证与边界

- `tools/tests/test_windows_parent_startup_preflight.py`：Windows 11 本机 Python 3.13，2/2 通过；TEMP/TMP/RUNNER_TEMP/Python cache 均指向 `D:\\A35Temp`，代码仓库在 D 盘。
- `tools/tests/test_preflight_packaged_production_startup_windows.py` 本机无法导入：系统 Python 3.13/3.14 均未安装 `cryptography`，而被测模块顶层导入 HTTPS smoke 依赖。本轮未临时安装依赖或写入 C 盘。该测试已有 hosted CI 覆盖；A35 workflow run `41026213054` 全 12 jobs success。此导入耦合不属于本 A36 前置盘点范围。
- `git ls-files` 未返回已跟踪的正式产品公钥文件；仅核对了路径/文件追踪元数据，没有读取任何私密工作台目录。
- 未触碰用户账户 Credential Manager、产品安装目录或数据库；未启动监听器/服务；未访问客户数据；所有本地测试临时路径在 D 盘。
- 结论只代表现有源代码与验收证据的盘点，不代表 Windows 11 Pilot 部署、真实 trust、安全装配或 Gate/Release 验收通过。

## 下一步

P51-A37：形成 Windows 11 Pilot 正式输入登记与安全就绪检查路径。先定义非秘密配置引用/责任人与验收证据清单，并为后续真实材料建立“只校验、不回显”的本机/hosted 分层检查；密钥值不得进入仓库、日志或 GitHub Artifact。若正式材料仍缺失，继续推进不依赖其的 Pilot 包离线准备工作。
