# CR-OUT-032：OutputArtifact 用户检索与下载关联

- 日期：2026-11-06
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P35 → P36
- 状态：P35 PASS_WITH_LIMITATION；P36代码候选已准备提交，GitHub hosted验收待完成
- 来源：CR-EXEC-002优先形成Windows 11受控内部Pilot；P34B已证明内部生成文件发布，而用户侧无法从OutputRequest定位Artifact。
- 基线：冻结 API Contract V1 的 OUTPUT_REQUEST_GET/LIST、OUT-02、Document/DocumentVersion/Storage合同，CR-OUT-028/031；P34B PASS_SCOPE_LIMITED。

## 证据与问题

OutputRequest固定读投影仅返回状态及请求/Job/Execution等引用；输出历史UI只有状态且提示不代表可下载。P34B验证内部Storage与数据库发布链，没有产品HTTP/Worker启动。Document已有项目授权的元数据/版本读取以及完整性复核内容下载服务，但未提供从OutputRequest到Artifact/DocumentVersion的安全关联入口。两组opt-in router存在不能当作Windows服务已挂载的证据。

## 方案比较与选择

- 方案A：在现有OutputRequest GET/LIST增加Artifact和DocumentVersion字段。实现直接，但改变冻结projection及要求精确字段匹配的前端合同，影响既有调用方。
- 方案B（选择）：新增独立的项目范围只读Artifact引用GET endpoint；原有GET/LIST响应保持不变。只有请求SUCCEEDED、唯一绑定Artifact为AVAILABLE且Project/Document/Version/FileObject/Hash/size/MIME关系一致时，返回固定Document/Version身份和受控内容route。字节仍经既有Document下载service读取。
- 方案C：前端枚举项目全部Document并猜哪个文件属于请求。无法证明归属且会有歧义，拒绝。

## 实施边界

- 不增表/字段/Migration，不改既有API response、Output状态Owner、生成Worker、Storage或TraceLink基线。
- 新route只投影固定Artifact、DocumentVersion身份及必要元数据；不得返回Storage locator、Secret或生成正文。
- 查询同时限定 ProjectId + OutputRequestId；在项目读取授权事务内验证Artifact AVAILABLE、Document GENERATED_ARTIFACT、Version/FileObject AVAILABLE及精确关联。缺失/冲突/不可用均失败关闭。
- 使用受保护Document content endpoint；内容Hash与大小由既有下载服务验证。前端仅在请求SUCCEEDED且新接口返回合同完整引用时提供下载。
- 新route沿现有Windows Output read opt-in composition扩展；不宣称默认服务已挂载。若Pilot composition缺Document Download router，另行记录装配任务，不回退为直读文件。

## 风险、迁移与回滚

风险为Artifact与Project边界漂移、非AVAILABLE文件过早可见、或projection漏做权限复核。以复合SQL关系、项目读取授权、AVAILABLE过滤、Document下载二次授权与Hash/大小复核控制。
无Schema/API迁移。回滚移除新增route/service/Repository及前端入口；不删除Artifact/Document/DocumentVersion，不改变已发布历史。

## 验证计划

GitHub hosted Windows Server 2025 D: + 临时 PostgreSQL 18 + 纯合成数据。增加Application/Repository/HTTP权限/异常测试、PG18真实projection断言；前端严格解析、SUCCEEDED下载按钮、其他状态无入口和下载触发测试；后端全量/wheel、前端全量/build。随后运行可独立成功的父包/A17/A34/A35/A50。P25 initdb诊断继续暂停，不能阻止本项，也不能将整体workflow称为全绿。

## P36 Hosted前静态复核偏差（2026-11-06，修复前记录）

新增PG18 verifier helper放置在连字符目录，但P33 smoke verifier用Python模块导入时采用了下划线路径，二者不匹配，预计会在验证器导入阶段失败。此偏差只影响测试接线，不改变产品逻辑或验收范围。修复：将helper移动至名称匹配的下划线目录并统一import，再运行新Hosted全链。