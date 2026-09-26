# CR-DOC-005：升版 UploadIntent 的上传文件显示名

日期：2026-09-25；状态：按 CR-EXEC-001 持续授权，增量 `0024` 已实施并验证。范围：Phase 2 / DOC-03-A04-A03-P01。原 Gate 2 冻结提交 `64cdf09` 和 `0023` 历史保留，不倒写。

## 来源、证据与冲突

冻结 API-02 `DOCUMENT_UPLOAD_CREATE` 要求新建 Document 或给既有 Document 升版时均声明 display name；DM-03 要求 FileObject 保留原始文件名元数据。当前 `doc_upload_intents.original_display_name` 在新建模式必填，在既有目标模式却被 `ck_doc_upload_intents__existing_document` 强制为 NULL。DOC-03-A04-A02 的内部命令同样禁止既有目标携带它。由此无法为升版 Content 建立可信文件名/扩展名检查，不能直接进入流式写入。

## 方案比较与选择

- 不选从既有 Document 的 `original_display_name` 复制：历史文档名不一定等于本次上传文件名，且会伪造请求事实。
- 不选在 Content 时临时接收另一个文件名：与冻结创建请求契约相悖，重试时易发生不一致。
- 选择复用 Intent 的 `original_display_name`，其语义固定为本次上传文件名；新建 Document 时同时作为初始显示名，既有 Document 时只用于新 FileObject，不改 Document 身份。调整既有目标约束，并对所有新 INSERT 要求该值；旧缺名记录只允许过期/终止，不自动回填。

## 影响、迁移、回滚

新增 ORM/增量 Alembic `20260925_0024`，不改冻结 HTTP 路径、请求字段、技术栈或其它 Root。升级前备份；有数据升级保留旧记录原值，禁止通过 Content 接受缺名的旧意图。降级前若出现既有目标且带显示名的记录须拒绝，不删除追溯历史；无此数据时恢复旧约束与触发器。创建服务改为既有目标也要求上传显示名，Token/收据字段不变。失败事务不写入 Intent/Audit/收据。

## 验证计划与剩余风险

Windows 11/Python 3.13 后端 464 项无失败（2 项符号链接场景因当前账户权限跳过）；PostgreSQL 18 临时库已验证空库与已有旧形态数据升级、空/旧形态降级再升级、ORM 差异为零、旧记录不变、新 INSERT 必须有文件名、身份不可改、新形态非空降级拒绝；A02 合成创建回归和开发 wheel 通过。临时库已删除，服务已停止。流式字节、MIME/签名、正式授权与公开 API 留 DOC-03-A04-A03 后续子任务；本 CR 通过不等于 Content 已实现。
