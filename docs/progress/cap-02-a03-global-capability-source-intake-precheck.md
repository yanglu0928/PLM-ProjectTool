# CAP-02-A03：GLOBAL 标准能力固定文档来源入口编码前检查

日期：2026-10-24；状态：`SOURCE_PASS / SYNTHETIC_POSITIVE_EDGE_PG_PASS`。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `CAP-02-A03`：只解决部署管理员无法从用户界面建立 GLOBAL `STANDARD_CAPABILITY` 可用固定文档版本的问题；不在本项创建/批准 CapabilityBaseline。|
|输入基线|Gate 2 冻结 Document GLOBAL upload create/content/commit/abort 与 GLOBAL document/version read；`CAP-02-A02` 只读 Capability 页已源码验收。现有 `ProjectDocumentUploadView` 与三个上传客户端只处理 PROJECT，不能把 PROJECT 文档当 GLOBAL 来源。|
|前置|后端 GLOBAL 四个上传接口及 DocumentReadClient GLOBAL 只读路径已存在；本项仅前端添加 GLOBAL 传输与管理员入口，复用 SessionClient 私有 CSRF、同源/幂等保护。需继续保持上传 Token 只在内存、写操作不确定结果不换 Key 自动重试。|
|模块/实体/API|Document GLOBAL upload intent、二进制、commit/abort；完成后只以 GLOBAL Document/DocumentVersion 的 `ACTIVE`/`AVAILABLE` 读取事实供后续 CAP-02-A04 选择。不得直接引用本地文件路径或把文件名推定为已上传/已解析。|
|权限|界面仅 DeploymentAdmin 且未强制改密可用；后端重新验证 Session/CSRF/License、GLOBAL 操作资格。项目成员不得借项目权限写 GLOBAL。|
|验收|各步骤严格响应、文件哈希、Location/no-store、原操作号、失败/中断清屏与恢复提示；管理员正向及普通成员/匿名拒绝；定向/完整前端测试、typecheck/build，再单独安排 Windows 11 Edge/PG 合成文件实测。|
|风险|真实标准能力库文件含内部资料，不自动扫描/导入或外发；现有项目上传页不能直接改成 GLOBAL 兼容而不复验既有 PROJECT 行为。完成 GLOBAL 文档入库也不等于 CapabilityBaseline 已创建或获批。|

此项无 Schema/API Breaking Change，无外部模型调用。待实现后独立关闭；后续 CAP-02-A04 才能选择合格固定版本创建基线，再依正式 Review 获取当前批准版本。Pilot/Gate 仍 `NOT_READY`。

## 实施与源码验收

- 在现有 Document UploadIntent/Content/Finalize 客户端增加 GLOBAL 专用路径，SessionClient 私有 CSRF/上传凭证/幂等边界保持不变；原 PROJECT 调用复用固定路径底座并完整回归。
- 新增部署管理员独立 `STANDARD_CAPABILITY` 新文档上传页。只允许 GLOBAL 新文档，不把项目文档转作全局来源；三步操作、未知结果原操作号确认重试、显式终止、会话变化清屏和提交后独立 GLOBAL Document/AVAILABLE 固定版本读取均有界面状态。
- 新增 GLOBAL 传输 3 项、页面权限/正向/未知/终止/重放/会话变化 6 项；关联定向及前端全量 166 文件、1896 项 PASS，TypeScript 检查、Vite 构建 PASS。现有 PROJECT 上传与 Auth 客户端定向 274 项 PASS。
- 尚未执行真实 Edge/PG 合成文件端到端；不能由回执推定已解析、已批准 CapabilityBaseline，亦不能把本地标准能力库文件自动写入系统。

后续 `CAP-02-A03-P02` 已在 Win11 固定非发行候选中以合成文件完成真实 Edge/隔离 PG 上传、GLOBAL `ACTIVE` 文档及 `AVAILABLE` 固定版本反读、三类上传 Audit；首轮验收 SQL 列名错误和同候选复验退出 0 见 `docs/progress/cap-02-a03-a04-p02-packaged-edge.md`。上段保留当时源码验收事实，不将其改写为首轮已通过。正式来源、批准与 Pilot 仍待。
