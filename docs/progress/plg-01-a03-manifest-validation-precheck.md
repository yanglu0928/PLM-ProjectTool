# PLG-01-A03：版本化 Plugin Manifest 解析与入口路径校验编码前检查

- 日期：2026-11-03
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT
- Phase/WBS：Phase 2 / PLG-01-A03
- Change Request：CR-PLG-002（格式边界先记录）
- 上一项：PLG-01-A02 Ed25519 verifier PASS_SCOPE_LIMITED；正式Trust source材料缺失
- 执行环境：GitHub hosted Windows Server 2025；临时工作目录限定runner D盘；禁止用户本机/C盘执行

## 单一目标

新增 Plugin Owner 的有界只读 Manifest parser：校验版本化JSON结构、操作/依赖声明与相对入口路径，并返回不可变结果及canonical manifest SHA-256。本项不读取ZIP、不解压、不执行、安装、签名验真或改变Package状态。

## 编码前检查

|检查|证据与结论|
|---|---|
|正式基线|ADR-005要求加载前验证Manifest、Plugin API、OS、入口和声明依赖；DM-04定义不可变Manifest snapshot与operation/dependency语义；API-03包导入只接受开发者签名包。具体JSON属性未冻结，故先建CR-PLG-002。|
|当前PoC|POC-08 parser只验证name/version/API/OS/supported_formats/entry_point及入口SHA-256。PoC文档明确签名字段不具开发者身份信任；不直接复用其JSON为正式包。|
|当前生产实现|A01提供Package/operation/dependency存储元数据；A02只验证完整archive bytes的Ed25519签名。当前没有生产Manifest parser、包导入、Trust root或解包器。|
|实现Owner|仅 `modules/plugin/application`；不从Output或其他模块读写私有数据；不调用文件系统/网络/子进程。|
|格式决定|CR-PLG-002定义严格 `plm.plugin.manifest.v1`；根/嵌套字段allowlist、版本目标、operation/dependency约束、UTF-8与重复key规则。未知字段拒绝，不默默忽略。|
|入口安全|只规范化字符串；拒绝绝对、drive/UNC、反斜杠、NUL、空段、`.`/`..` 和非规范路径。真正Archive展开/符号链接/大小炸弹保护另设WBS。|
|验收标准|有效合成manifest通过并输出不可变数据和稳定指纹；重复键/未知字段/类型/OS/API/依赖/操作/路径/大小/深度/节点异常均失败关闭；后端全量/wheel和hosted全链。|
|风险|JSON值约束不等于完整ZIP安全性；未验签的Manifest不可信；Resolver仍只消费在后续pipeline顺序中签名验证后的数据。无客户包/真实外发。|
|偏差/回滚|基线未指定具体Manifest JSON，CR-PLG-002固定首个版本化格式；无DB/API/Migration。失败则包导入继续关闭，撤销未发布parser。格式演进须新schema version。|
|Secret与临时数据|仅合成JSON和恶意路径字符串；不生成/持久化密钥、不含客户资料。执行只限GitHub runner D盘temp。|

## 编码文件范围

新增 `apps/backend/src/plm_assistant/modules/plugin/application/manifest_parser.py` 与 `apps/backend/tests/unit/test_plugin_manifest_parser.py`，更新CR、STATUS、CHANGELOG及结果记录。若实现发现需要解包/外部文件或新持久字段，停下并另建CR。


## 首轮云端验收失败记录（2026-11-03，修复前）

GitHub hosted run [41571211968](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41571211968) 后端3,888项中有1项失败：`test_entry_point_rejects_absolute_drive_unc_traversal_and_ambiguous_paths` 中 NUL 字符入口路径被安全拒绝，但 `_entry_point` 在路径专属校验前调用通用 `_text`，因此错误码为 `PLUGIN_INVALID_MANIFEST` 而不是 `PLUGIN_INVALID_ENTRY_POINT`。没有路径穿越绕过；这是失败分类与测试合同不一致。其余后端测试、前端/PG18/A50通过；包组装与A17/A34依赖作业被跳过。先记录后修正。

编码复核另发现两项专项用例构造不充分：深层结构夹具被根字段白名单提前拒绝；空依赖列表测试未先断言合法空列表。修复时会将深层对象放入有效根字段，并单独断言空依赖有效，确保实际覆盖目标边界。
