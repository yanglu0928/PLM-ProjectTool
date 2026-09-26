# DOC-03-A04-A03-P01 Content 文件名契约前置

日期：2026-09-25；结果：Schema/内部命令 PASS，流式 Content 尚未实现。依据冻结 API-02、DM-03、CR-DOC-005 与 DEC-20260925-102。

发现 `0023` 错误地禁止既有 Document 升版意图填写 `original_display_name`，与创建请求必须声明 display name 及 FileObject 原始文件名元数据冲突。`0024` 放开既有目标的该字段，并对新 INSERT 强制必填；既有历史缺名记录不回填、不允许后续 Content 使用。新建 Document 的原字段行为不变，升版时该字段只指本次文件，不更改既有 Document 身份。

验证：Windows 11 后端 464 项无失败、2 项符号链接权限跳过；PostgreSQL 18 独立临时库空/有数据升级、可逆状态降级、新形态拒绝降级、约束/不可变触发器、ORM 差异及 A02 创建回归通过；开发 wheel 通过。无公开 API、新依赖或客户数据外发。目标库升级前须备份并执行到 `0024`；只有有新形态历史时不能普通降级。

下一项 DOC-03-A04-A03-P02：按冻结契约实现有界流式 Content 校验和受控暂存，再处理 FileObject/STAGED 原子登记与重传/崩溃恢复。当前不得将 Content、三步上传或 Gate 3 标为 PASS；正式 Session/License/Project 权限、密钥来源、Server 2025/Debian 13 及最终程序包仍未验证。
