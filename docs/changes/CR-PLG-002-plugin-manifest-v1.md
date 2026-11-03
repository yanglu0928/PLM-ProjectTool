# CR-PLG-002：版本化 Plugin Manifest V1 解析格式

- 日期：2026-11-03
- 状态：APPROVED_BY_CONTINUOUS_USER_AUTHORIZATION / IMPLEMENTATION_IN_PROGRESS
- 适用 WBS：PLG-01-A03
- 依据：ADR-005、Gate 2 冻结 DM-04/API-03/SC-01～03、POC-08现有Manifest样例、用户2026-09-24持续自主执行授权

## 问题与决定

冻结基线要求校验Manifest、入口、声明操作、兼容性与依赖，但未固定完整JSON字段名/版本化格式。POC-08现有manifest只代表PoC：其 `sha256:<entrypoint hash>` 不是签名，也没有生产operations结构。为使生产Package有确定、可拒绝未知字段的输入合同，规定只读 parser 接受 `plm.plugin.manifest.v1`：

- 根字段严格为：`schema_version`、`plugin_id`、`name`、`version`、`plugin_api_version`、`supported_os`、`architecture`、`entry_point`、`operations`、`dependencies`。
- OS取值为 `windows-11`、`windows-server-2025`、`debian-13`；首版架构为 `x86_64`；每项版本为明确字串，不接受动态latest/current。
- `operations` 为去重对象列表，字段为 `operation_id`、非空 `output_types`。它们是声明，不构成安装或授权。
- `dependencies` 为去重对象列表，字段 `name`、`version_spec`、`kind`；kind只接受 `PYTHON/OS/SYSTEM`。仅声明、不解析、不下载、不安装。
- `entry_point` 只接受规范相对 POSIX 路径；拒绝绝对路径、父级遍历、反斜杠、NUL、空/点段和Windows drive/UNC形式。
- JSON拒绝重复键、非UTF-8/非有限数、未知字段、超限/超深结构。Parser只返回不可变结构与canonical digest，不访问文件系统、解压、导入或启动代码。

## 影响、兼容性与风险

- 无数据库/API/ORM/Migration变化；输入为有界manifest UTF-8 bytes。
- 对齐DM-04包元数据、operations/dependencies子表及ADR-005兼容检查职责，不变更Gate 2语义；新版本若需字段必须新增 schema version 或另建CR。
- POC-08旧JSON fixture不是该生产格式；它的摘要字段不得视作签名，也不自动转换成生产Package。
- 路径字符串检查不等于安全归档解压。本WBS不遍历ZIP内容/符号链接；真实导入/解压须另行实现拒绝路径穿越、链接与资源耗尽。
- 不验证发布者信任。生产signer root/撤销源缺失，顺延独立WBS；不得把Parser通过或合成验签标为Package VERIFIED。

## 回滚与验证计划

- 无持久格式/迁移，无生产存量。若验收失败，保持导入入口关闭并删除未发布parser；以后以新 schema version 兼容，不改写旧Manifest。
- 测试精确合法结构、所有字段错误/未知字段、重复JSON键、UTF-8、深度/大小/节点限制、重复operation/dependency、OS/架构/依赖kind及路径边界/Windows路径/归一化攻击。
- 后端全量测试/wheel及GitHub hosted Windows Server 2025 PR链；仅合成/恶意字符串输入，无客户数据、外网包或真实插件代码。所有运行仅在hosted runner D盘temp。

本CR先于编码提交；详细检查见 `docs/progress/plg-01-a03-manifest-validation-precheck.md`。
