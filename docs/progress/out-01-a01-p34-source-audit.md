# OUT-01-A01-P34 编码前源码审计：Generated Artifact 发布依赖

- 日期：2026-11-05
- 结论：P34 原范围需拆分；新增 P34A DocumentVersion Owner 前置，P34B Storage 协调仍待
- Change Request：CR-OUT-030；拆分及差异登记 CR-OUT-031
- 执行方式：只读检查 GitHub 功能分支；未运行本机项目代码

## 已核实源码路径

- document/application/commit_upload_version.py：上传版本Owner先验证既有可用文件，再调用Repository建版本；验证要求非空FileObject和AVAILABLE文件证明。
- document/infrastructure/upload_version_repository.py：_check_document明确拒绝document_category == GENERATED_ARTIFACT；_snapshot要求FileObject状态AVAILABLE、locator为最终路径且available_at已设置。commit在单事务插入AVAILABLE DocumentVersion与UPLOAD source ref，再推进Document.latest_version。
- document/application/publish_file.py 与 document/infrastructure/file_publish_repository.py：现有FileObject发布/恢复是用户授权和用户Audit语义；输出Job是SYSTEM/原请求人归属语义，不能直接假装成普通上传操作。
- output/application/complete_generation.py 与 output/infrastructure/complete_generation_repository.py：P33在单事务验证生成Claim和已存在AVAILABLE的Artifact、Document、DocumentVersion、FileObject，并原子完成OutputRequest、Job及SYSTEM Audit；不会创建文档版本或执行文件IO。
- ADR-008所需LocalFileStorage提供内容校验、同卷不可覆盖提升和受限恢复分类，但本身不变更数据库。

## 结论与边界

当前缺少“系统生成的DocumentVersion”内部提交Owner。故不能先把Storage文件发布与P33串起来后声称完整安全：版本行必须在FileObject AVAILABLE之后创建，而普通上传Owner主动禁止GENERATED_ARTIFACT。按CR-OUT-031把P34拆成P34A（最小内部版本Owner）和P34B（文件发布协调）。P34A编码前还需审查DM-03的DocumentVersion source_ref允许的枚举、执行绑定可用字段、幂等收据适用性和锁顺序；未完成这一步前不编码，不新增Schema/API/default composition，不绕过现有Owner。