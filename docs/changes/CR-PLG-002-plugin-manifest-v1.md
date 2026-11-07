# CR-PLG-002：版本化 Plugin Manifest V1 解析格式

- 日期：2026-11-03
- 状态：APPROVED_BY_CONTINUOUS_USER_AUTHORIZATION / PASS_SCOPE_LIMITED
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


## 首轮验收失败记录（2026-11-03）

Hosted run 41571211968 后端3,888项中1项失败：含NUL入口路径安全拒绝，但因错误分类顺序返回 `PLUGIN_INVALID_MANIFEST`，专项合同期望 `PLUGIN_INVALID_ENTRY_POINT`。详见A03编码前检查的失败记录。测试复核发现深度及空依赖专项夹具断言不足，修复前已一并记录。安全拒绝没有绕过；A03保持未通过，等待定向/全量云端重跑。


## 第二次验收复现（2026-11-03）

Run 41571779122 对前一次入口NUL错误码修复仍得到同一失败，表明单纯调整 `_entry_point` 内部检查顺序未使全流程映射一致。修复前再次登记。下一修正会在通用Manifest结构检查前执行入口专属预检，并以subTest报告准确的路径样例。当前状态仍未通过。


## 第三次验收根因（2026-11-03）

Hosted run 41572410413显示12个entry-path子例失败。根因为测试 `reject()` helper 将Python dict原样传给仅接受bytes的Parser，导致输入类型守卫提前返回通用错误；路径与大部分结构负向测试此前均未真正执行目标解析逻辑。先前两次对错误分类的实现调整未被有效测试覆盖。修复helper为先JSON/UTF-8序列化fixture后再调用，保留直接bytes用于坏JSON/无效UTF-8用例。当前A03仍未通过。


## 测试根因纠正及最终验收（2026-11-03）

- 对先前3次失败记录进行纠正：首轮并未证明“NUL错误分类”；原因是 `reject()` 将dict fixture直接传给bytes-only parser，目标代码没有执行。第二/三轮也同样未测到具体Manifest/路径字段。详见 `docs/progress/plg-01-a03-manifest-validation-result.md`。
- 最终修正commit `9abfa92316f0a91e1e20360a858d794173e4f7bf` 将dict fixtures序列化后再传parser；最终run [41573036147](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41573036147) 13/13 jobs成功，后端3,889全通过并构建wheel，前端/PG18/父包/A35/A17/A34通过。
- PLG-01-A03为 `PASS_SCOPE_LIMITED`。本结果只覆盖合成Manifest bytes；不覆盖ZIP解包、生产发布者trust、安装或执行。
- 下一项：PLG-01-A04正式Trust source/轮换/撤销编码前检查。
