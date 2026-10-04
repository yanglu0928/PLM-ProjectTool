# WFL-01-A07-P03-A02：Document 固定来源内部证明

日期：2026-10-02。基线：Gate 2 原冻结提交 `64cdf09`，偏差依据 `CR-WFL-005`、决策 `DEC-20261002-603`。状态：**Document 内部 Port PASS；Evidence Owner 未接、Checklist/Gate 写关闭**。

本任务只在 Document Application 层组合已存在的受权读取与新建固定 ParseRecord 锁。`prove` 要求调用方维持同一事务直至引用写入提交；先锁 Document/Version/File 的当前可用来源事实，再按有无 ParseRecord 分别验证私有文件快照，或锁 ParseRecord/ResultRef 并复用解析结果读服务验证物理文件、结果字节和 JSON 内的固定源摘要。所有 ID、Scope/Project、Hash、解析器字段必须与锁中事实一致；返回不含路径，解析字节仅供未来内部 Evidence Owner 使用，`repr` 不显示。

验证：单元新增 6/6，相关读取回归 16/16；一次性 PostgreSQL 18 对 Document、Version、File、ParseRecord、ResultRef 五行持锁时第二连接 `FOR UPDATE NOWAIT` 均返回 `55P03`。合成私有源文件与解析结果真实写盘并按哈希通过，源文件篡改、解析结果篡改、撤权、错误项目和失败 ParseRecord 均拒绝。后端全量 1838 通过/3 跳过；本地 wheel 构建 SHA-256 `8c5c29919b677716b118a68c4006e800524dfc10256755413eb9c633d19a7876`。

兼容/升级/回滚：无公开 API、Schema/Migration、依赖或客户数据迁移；可不装配后续 Owner 并保留原普通读取。物理文件不受数据库事务锁控制，本证明只声明读取时的已验证快照，不保证提交后文件永不变；后续新引用/StageGate 必须重新验证。GLOBAL 普通访问仍只有 DeploymentAdmin，项目经理窄标准引用尚未实现；Evidence 当前 ELIGIBLE、locator、Review/例外 Owner、真实浏览器与正式发行信任/法律、Server2025/Debian/UAT/Gate 都未据此通过。禁止把本项标成完整 Workflow 或可发行包。
