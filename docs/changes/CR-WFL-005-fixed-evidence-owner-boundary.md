# CR-WFL-005：Workflow 固定 Evidence Owner 受权与同事务来源证明

日期：2026-10-02；来源：`WFL-01-A07-P02` 编码前核查；状态：`DESIGN_RECORDED / IMPLEMENTATION_PENDING`。原 Gate 2 冻结提交 `64cdf09` 不修改，CR-WFL-004 的记录/引用结构与既有历史保持。用户 V1.1 持续授权下先记录偏差、边界与验证，再分任务实施。

## 证据与冲突

冻结六阶段 `EVIDENCE_FIXED_PROJECT_V1` 允许同项目 PROJECT 及受权 GLOBAL 标准引用，要求当前可访问、固定版本、ELIGIBLE、来源定位和制品完整；Checklist PASS/WAIVED 与后续 Gate 必须在调用方事务重验。现有 Evidence/Document 的 GLOBAL 普通读取仅 DeploymentAdmin，项目经理不能借它完成受控标准引用；直接开放 GLOBAL 列表/下载会扩大信息权限。现有 Evidence Viewer/Document ParseResult 读取进行独立事务及文件重验，不能保证 Workflow 提交时的 DocumentVersion/ParseRecord 仍为同一受锁事实。`SqlAlchemyEvidenceEligibilityRepository.lock` 只给资格/版本及 Document ID，缺 locator/固定 ParseRecord 来源；仅凭该记录或 UUID 无法证明完整引用。Review Subject/ApprovedException Owner 仍另缺，故当前 Checklist 写入口必须保持关闭。

## 方案比较与选定

1. 复用普通 GLOBAL 读取并赋予 PM 部署管理员资格：拒绝，越权且混淆 Scope。
2. 只支持 PROJECT 或只支持整文档，永久跳过 GLOBAL/解析节点：拒绝，缩减冻结业务能力。
3. **选定**：在 Document/Evidence 模块的 Application Interface 增加仅供受控业务引用的固定来源证明，调用方持当前 Session、目标 Project 与实际角色进入同一写事务；Document/ParseRecord 锁与已验证文件/解析结果摘要关联，Evidence Owner 锁固定记录、当前资格与版本并调用来源 Port。GLOBAL 仅允许明确的标准类别、当前项目 PM 可引用，但不因此获得 GLOBAL 列表、正文下载或管理员权限；PROJECT 必须同 ProjectId。Unknown/旧缺 ParseRecord、失效/撤销/模板冒充事实、文件或解析摘要漂移全部失败关闭。返回最小 typed Evidence 观测事实而非客户正文/路径。Review/例外必须由各自实际 Owner 后续独立证明，不能由本 Port 假造。

## 差异、影响与回滚

这是内部受权 Port 与业务引用策略补充，非新公开 API、非通用 GLOBAL 读取授权、非 Schema/技术栈改变；现有普通读取/上传和旧 Evidence 行不自动改写。若实现失败，可不装配 Owner 并保持 Checklist/Gate 写路由关闭；已有历史及公开 API 不变。若将来需 Schema 增量，须单独 CR 与空/有数据 up/down 验证，不在本 CR 静默添加。合法已提交历史不因之后来源变更而改写，但新记录/Gate 不得沿用过期观测。

## 验证计划与开放风险

分任务验证 Document 固定 DocumentVersion/ParseRecord 同事务受锁读取与实际文件 Hash、Evidence locator/fingerprint/当前 ELIGIBLE 复核、PROJECT 跨项目隔离、GLOBAL 标准类别 PM 引用但普通 GLOBAL 读取仍拒绝、非标准/模板/撤权/失效/篡改/并发/回滚、零正文或路径泄漏。再与 Workflow 当前 Checklist/Stage/Project/Session/CSRF/License/Audit/收据合成集成，并补真实 Review/例外 Owner；未齐之前不开放 PASS/WAIVED/Gate。Server 2025/Debian、正式信任、浏览器/UAT/性能/Gate 仍按独立证据验收。
