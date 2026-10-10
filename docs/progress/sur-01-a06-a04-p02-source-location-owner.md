# SUR-01-A06-A04-P02：Survey 来源定位内部 Owner 与 Adapter

日期：2026-10-06。结论：`SUR_01_A06_A04_P02_SOURCE_LOCATION_INTERNAL_PASS`。下一项：`SUR-01-A06-A04-P03` 严格 HTTP、Windows 组合与真实 HTTP/PostgreSQL 验证。

## 实现

- 新增 Survey-owned `SurveySourceLocationService`，在一个事务中重验 License、Session、`SURVEY_VERSION_GET` Project 权限和精确 Survey/Version/question/source ordinal；Session token 不进入 repr。
- Survey 仓储只读取精确固定 source identity；Handover、Capability、Document 各自拥有历史/公共解析 Adapter，Survey 不直接查询这些模块私表。
- Handover 返回公共 analysis/version/item 与经 Evidence 表再次核对为同 Project 的 Evidence；历史项仍可追溯，但 `current_eligibility` 只在当前 ACTIVE/APPROVED/合格状态为 true。
- Capability 返回公共 baseline/version/item；内部 Adapter 保留有序 Document/Evidence 引用，但 Project 调用结果不扩大 GLOBAL 可见性，只给公共 record ref 和 `NO_AUTHORIZED_LOCATION`。
- PROJECT TEMPLATE 返回固定 DocumentVersion location；GLOBAL TEMPLATE 不继承 Project 权限。MANUAL 返回 `MANUAL_SOURCE_NOT_FIXED`，缺失目标返回 `SOURCE_TARGET_UNAVAILABLE`。
- 所有公开结果均不含内部 `*_row_id`、正文、文件路径、locator 或下载 URL；最终 Evidence 原文仍由既有 Viewer 重验。

## 验证

- 定向 16 项通过：四类来源、历史/当前分离、GLOBAL 隔离、缺失/非法 ordinal、权限 operation 和 Session 脱敏。
- 新模块导入与 compileall 通过。
- Windows 11/PostgreSQL 18.6 隔离库运行真实 ORM/事务 Adapter：四类固定来源、公共标识、GLOBAL withholding、Handover/Capability 状态漂移后仍可追溯但不再当前合格、Survey/Audit 零写入均通过；标记如上。
- 后端完整回归：依赖齐全 Python 3.13 环境 2854 项通过、3 项跳过。第一次误用缺少 `pgvector` 的旧验证 venv 得到 19 个导入错误；改用完整既有验证环境后全量通过，该次仅为环境偏差，不作为产品失败。
- wheel：1059 entries，包含全部新 Owner/Adapter；SHA-256 `d4667e34e0810d99499be0d86ae023bb147ba1f2065fe99a08660be07c871adf`。

## 影响与剩余项

无 Schema/Migration、现有 API、角色、依赖、配置、Secret、网络或外发变化；内部代码尚未挂 HTTP。删除新增 Service/Adapter 与 `get_source` 即可回滚，既有 Survey 历史不变。P03 完成前 location 端点仍为 404；前端真实按需定位、写交互、Round/Response/Conclusion、Gate 3/UAT/发行仍未通过。

