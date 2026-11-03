# PLG-01-A06：Plugin ZIP安全只读解析与签名Manifest联合验证编码前检查

- 日期：2026-11-03
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT
- Phase/WBS：Phase 2 / PLG-01-A06
- 输入变更：CR-PLG-004（先固定ZIP envelope、安全边界、资源上限及验证计划）
- 前置：PLG-01-A01/A02/A03/A04/A05均PASS_SCOPE_LIMITED；A05云端run 41579068045全13 jobs成功。
- 执行约束：代码测试只运行于GitHub hosted CI；内存合成ZIP/签名，不用本机、不读客户包、不上传artifact。

## 单一目标

在不落盘、不解压、不安装、不启动插件的情况下，把完整ZIP字节的安全只读结构检查、根目录Manifest解析、声明EntryPoint成员确认和外部detached signature验签组合为一个服务，杜绝Manifest/signature/EntryPoint对象错配。

## 编码前检查

|检查|证据与结论|
|---|---|
|输入基线|CR-PLG-001定义Ed25519全归档SHA-256/key-ref签名；CR-PLG-002定义有界Manifest parser和POSIX entry_point；A05 packaged resolver仅从包内公开trust manifest提供Active key。|
|格式确认|CR-PLG-004先于编码固定ZIP + 根manifest.json + 包外签名；POC-08旧manifest signature仅是EntryPoint摘要，不作身份信任。|
|模块职责|现有signature_verifier只验整包字节/签名；manifest_parser只解析bytes；A06以application service组合，ZIP读取仅在内存中。|
|成员处理|先限归档整体字节与central directory元数据；拒绝目录/文件冲突、重复或Windows大小写别名、非规范路径、链接/设备、加密、资源超限。仅解压根Manifest且使用硬上限；entry_point只核对归档目录项，不读取或运行。|
|实体/API/权限|不创建/更新PluginPackageRow或VerificationRow，不新增Migration、API、权限、持久化或用户动作。持久注册/状态转换在后续独立WBS。|
|失败关闭|manifest/ZIP不合法→稳定package/manifest错误；未知/撤销/空信任→PLUGIN_SIGNER_UNTRUSTED；签名/归档字节变化→PLUGIN_SIGNATURE_INVALID。任何失败不产生外部文件副作用。|
|验收|CR-PLG-004恶意ZIP矩阵、合法内存签名包、错配/篡改、Manifest/入口校验、Active/REVOKED/空Trust、成员资源限额；后端全量/wheel/hosted PR chain。|
|回滚与风险|只回滚应用检查器；格式及上限为新包合同，不自动导入旧POC；无DB数据迁移。性能按256MiB以内处理，验证完整归档hash为线性CPU成本。|
|Secret与数据|只生成内存合成key/signature和合成ZIP；不写artifact，不外传客户数据。push前Secret扫描、fetch expected head、fast-forward only。|

## 预计修改文件

- 新增 apps/backend/src/plm_assistant/modules/plugin/application/package_archive_inspector.py
- 新增 apps/backend/tests/unit/test_plugin_package_archive_inspector.py
- 新增 docs/changes/CR-PLG-004-plugin-zip-envelope.md（编码前先提交）


## 中央目录预检补充（编码提交前）

Python zipfile在ZipFile初始化时解析中央目录，无法先靠后续infolist()限制对象数。故实际实现必须先预检EOCD：最大尾窗65,557字节，最多4,096项，中央目录最多8MiB；拒绝ZIP64、多磁盘、自解压前缀及错位/注释长度不一致，再调用ZipFile并复核目录数量。该具体约束及原因已先追加到CR-PLG-004；新增对应恶意EOCD测试。
