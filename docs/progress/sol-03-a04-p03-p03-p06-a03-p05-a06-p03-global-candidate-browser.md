# SOL-03-A04-P03-P03-P06-A03-P05-A06-P03：项目 GLOBAL 候选 Win11 浏览器/PG 验收

日期：2026-10-09。结果：Windows 11 真实 Edge、可弃 PostgreSQL 18.6、合成来源与实际 FastAPI/前端构建的项目 GLOBAL 候选→DRAFT 创建链通过；正式发行/目标账户未验。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate 2 API-04、CR-SOL-018、DEC-1159、已验 A02～A06-P02。
- 前置：Win11 本地 Edge、PG18.6/pgvector 临时夹具、现有前端构建及真实 Document/Evidence/确认/发布合成来源具备；不使用客户正文或真实 Secret。
- 涉及模块/实体/API/权限：仅验证资产；项目 GLOBAL 候选 GET、OutlineVersion CREATE 与 Session/Project/License/PM 当前权限的现有组合，不改运行 ORM/Migration/API/权限。
- 验收：真实登录、已发布五字段候选、不出现管理员原名、项目固定 Section 与 GLOBAL 版本 DRAFT POST 201、PG 固定引用与单次审计、跨项目浏览器隐藏；上游合成夹具继续验证限制/撤回后候选不可见。
- 风险：合成密钥/许可不可代表正式信任锚，浏览器正例不可代表 Windows Server 2025/20 并发/发行。证据严格限定到 Win11 隔离环境，资源退出清理。

## 实施与证据

新增 `validation/sol-03-a04-p03-p03-p06-a03-p05-a06-p03-global-candidate-browser/`，复用真实来源与项目候选夹具，给合成管理员配置独立测试口令，创建项目 Outline/Section，使用既有 Windows 显式平台工厂装配当前证明、候选、章节/参考/需求列表及 OutlineVersion 写入口。临时 Uvicorn 提供当前前端构建；Edge 使用可弃 profile 执行登录、导航、选 Section/GLOBAL、人工确认及创建。验证脚本结束时关闭浏览器、HTTP 与临时 PG，未写正式环境。

执行命令：`$env:PYTHONPATH='apps/backend/src'; apps/backend/.venv/Scripts/python.exe validation/sol-03-a04-p03-p03-p06-a03-p05-a06-p03-global-candidate-browser/serve.py`，退出码 0，输出 `GLOBAL_CANDIDATE_EDGE PASS` 与本 WBS PASS。浏览器网络确认项目候选 GET 200、OutlineVersion POST 201；页面只显示“审定的合成标签”而不显示合成管理员原名，跨项目路由不展示候选。PG 确认 1 条 DRAFT、固定 `GLOBAL` 根/版本引用及 1 条 `SOL_OUTLINE_VERSION_CREATED` Audit。上游真实来源夹具同轮在发布前/后、资格限制和撤回后复核候选可见性；限制/撤回是在内部/PG 层验证，不宣称浏览器撤回操作已执行。脚本语法检查通过。

兼容/升级/回滚：只增验证脚本并向现有验证夹具透传 Audit，应用代码、DB Schema/Migration、冻结 API/角色/依赖均未变化；删除验证资产即可回滚，历史证据保留。正式服务账户 Vault/ACL/CA/SCM、Windows Server 2025 当前运行链、20 并发与 Gate 3/Release 仍待；Debian 13 实机按用户指令跳过。Vite 既有大 chunk 提示不影响本项，但发行性能需独立处理。

TraceLink：Gate 2 API-04 → CR-SOL-018 → DEC-1152～1159 → A02～A05 后端候选 → A06-P01/P02 前端 → 本 Win11 浏览器/PG 验收 → Gate 3/Release 独立证据。
