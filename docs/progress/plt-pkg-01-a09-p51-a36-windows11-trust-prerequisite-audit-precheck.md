# PLT-PKG-01-A09-P51-A36：Windows 11 Pilot 正式信任与安全运行前置可自动化性检查（编码前检查）

- 日期：2026-10-30
- 状态：检查中；本任务限定只读盘点与非秘密验收，不部署/启动产品。

当前Phase：Phase 2 Platform Core；Gate 3 尚未通过。
当前WBS：PLT-PKG-01-A09-P51-A36。
输入基线：冻结的 Architecture / Data Model / DB Schema V1 / API Contract V1；CR-EXEC-002 仅调整 Pilot/Release 顺序；`STATUS.md` 最新 P51 状态；P51-A33 启动诊断、A34/A35 隔离父包恢复证据。
前置任务：P51-A35 Windows 11 Home build 26300 D盘隔离父包替换/显式恢复 `PASS_LIMITED`，launcher 仍安全 `BLOCKED`；A35 已推送提交 `5c616e34`。
涉及模块：Windows 父包安全启动 preflight、产品 License 公钥资源装配、Windows Credential Manager 目标引用检查、服务账户/ACL、TLS 配置、Pilot 交付状态文档。
涉及实体：父包 `manifest.json` 的 `startup_preflight` 非秘密结果字段；`PLMProjectTool/Database` Credential Manager target 名称；License 既有信任锚。
涉及API：无；不得挂载业务 API 或启动监听器。
涉及权限：只读仓库、CI/现有合成验收记录与本机系统/文件元数据；不得读取 Credential Manager secret、私钥、API Key、客户数据；不得安装/注册服务、改 ACL、写用户安装目录、启动数据库或产品服务。
验收标准：逐项标明正式材料/环境输入、当前自动检查能力、是否可在无秘密输入时安全收口；验证现有诊断仅输出固定非秘密阻断编码且失败关闭；记录不可由自动化替代的真实证据与下游任务建议。Pilot/Gate/Release 不得因盘点而变更为通过。
风险：检查过度触碰当前账户凭据、创建虚假正式信任/证书/数据库信息、在 C 盘生成临时文件、把限制性状态误报为 Pilot Ready。

## 执行约束

- 本项不计划产品代码修改；若盘点发现可独立安全自动化且属于本项 Scope，先记录实现差异，再增加最小测试及回滚方式。
- 所有本地临时文件只允许落在 `D:\A35Temp` 或仓库 D 盘；优先执行静态代码/测试结构审查，不运行产品包。
- 结果按“已实现可自动验证 / 有输入后可自动验证 / 必须人工或目标环境验收 / 当前无材料”分类，绝不把字段占位或合成测试当作真实证据。
