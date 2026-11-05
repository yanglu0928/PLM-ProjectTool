# OUT-01-A01-P34A 编码前检查：系统生成 DocumentVersion Owner

- 日期：2026-11-05
- 结论：PASS_WITH_LIMITATION，可实现内部事务Owner；不接Storage、API、Worker或默认平台组合
- CR：CR-OUT-031
- 运行约束：代码及测试仅GitHub hosted/云端沙箱；不在用户本机/C盘运行

## 已核对的冻结数据边界

1. Migration 20260925_0022已冻结DocumentVersion、source ref及insert guard。source_kind受大写标识正则约束而无闭集枚举；source_owner_module/object_type/object_id/source_version_id可表达Output来源，OUT-01符合object type格式，无需Schema/Migration变更。
2. 插入DocumentVersion要求Document ACTIVE、Project ACTIVE、FileObject PERSISTENT+AVAILABLE且内容元数据一致；版本号必须是首版1或当前latest + 1，supersedes与Document.latest_version_ref必须匹配。版本字段不可变，DocumentVersionSourceRef append-only。
3. OutputRequest提供Project/Job/当前Execution/请求人；PluginExecution绑定request/project/job/attempt和成功manifest。Job Owner可验证current fencing Claim。FileObject使用PROJECT scope与Document usage，文件内容由既有复合唯一键绑定。
4. 用户上传版本Owner会拒绝GENERATED_ARTIFACT，因此不得借用它；P33仍是Artifact/OutputRequest/Job成功终结的最终权威。

## 最小Owner设计

- 新增document.application中的内部SYSTEM提交命令和Repository适配器，命令包含已校验Claim、worker ref、Document/Version/File IDs及SHA/size/MIME事实。
- 固定锁序：OutputRequest → Job claim校验 → PluginExecution → FileObject → Document。数据库触发器再次校验DocumentVersion顺序；所有元数据写、source ref与SYSTEM Audit在同一事务。
- 来源ref固定为source_kind=OUTPUT_GENERATION、source_owner_module=output、source_object_type=OUT-01、source_object_id=OutputRequestId、source_version_id=PluginExecutionId；metadata只保留非秘密资源身份及hash，不存文件路径或正文。
- 以FileObject唯一绑定和Document行锁阻止并发双版本；若已有版本，只有版本内容与Output Request/Execution来源、Document最新指针及Audit证据完全一致才返回重放事实，否则失败关闭。Job Claim必须在新提交时验证，旧fencing拒绝。
- 由P34A创建版本并推进Document.latest_version；不创建Document/FileObject、不提升/删除文件、不插Artifact、不完成Job。P34B负责Storage及跨资源恢复，P33完成Owner维持最终产物/Job成功事务。

## 验收

定向单测覆盖命令校验、错误scope/source/hash/mime、版本顺序、错Project/Request/Execution/Job/attempt/fencing、并发冲突、精确重放、变更后拒绝与Audit故障回滚；PG18 hosted verifier覆盖Migration head不变、版本与source ref同事务、Document指针、审计、历史不可变、空库升降重升和有数据降级拒绝。全量后端/wheel及既有父包验证。