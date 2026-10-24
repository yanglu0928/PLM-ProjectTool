# SOL-05-A03-P06-P01：SectionVersion CREATE 前端受控传输

日期：2026-10-12。结果：`SECTION_VERSION_CREATE_CLIENT_PASS`；仅 Session 命令桥接与 Solution 客户端，未新增创建页面或浏览器写链。

编码前检查：Phase 2；输入冻结 API-04 `SOL_SECTION_VERSION_CREATE` 路径/PM与实施成员权限、A02-P12 Windows 11 真实 HTTP/PG CREATE、现有 SessionClient CSRF/幂等桥接及 P05 历史读入口；前置满足。单一问题是把已验写接口做成前端严格受控命令合同。不改后端/API/Schema/Migration、权限或数据。风险是写请求可能已提交却因网络断开被误判失败、换号重试造成重复版本，以及 Artifact 裸引用混入首片；先登记 DEC-1186。

新增 `SessionClient.postProjectSectionVersionCreate`，沿用 same-origin Cookie、当前 CSRF、原 Idempotency-Key、大小上限和超时后不自动重试。`SectionVersionCreateClient` 仅接受 DocumentVersion 正文、规范标题、最多500有序且不重复的 Requirement/Evidence、最多100条且每组 ≤64KB 的声明；当前 Session 必须是本项目 PM/实施成员且允许提交。201 回执严格核对 Project/Section、版本状态、固定输入、计数、Location/Trace/no-store；不匹配或传输失败视为结果不确定。来源现时资格由后端同事务证明，客户端校验不代替它。

定向客户端 4 项通过，覆盖 201 固定回执/CSRF/Key、角色/跨项目/Artifact/重复来源/大声明拒绝、回执错位和异常安全映射。前端全量 130 文件/1745 项通过，`vue-tsc` 与生产 Vite build 通过；既存主 bundle >500KB warning 不影响本项运行。首次类型检查发现受控命令路径联合类型未包含新冻结路径，补入后全量复测通过。未跑本项真实浏览器写入（P03），前序后端真实 PG/HTTP 证据不代替它。

兼容/回滚：无迁移/后端接口/旧数据变化；撤未接页面的客户端与桥接即可回滚。下一项 `SOL-05-A03-P06-P02` 候选选择、原 Key/sessionStorage 恢复与创建页面；P03 单独做 Win11 Edge/PG 写链。正式目标账户/HTTPS/公钥、Server2025、Gate3/Pilot/Release 仍未通过，Debian13 实机按用户指令跳过。TraceLink：Gate2 API-04 → CR-SOL-003 → A02-P12 → DEC-1186 → 本 P01 → P02/P03 → VALIDATE/Review → Gate3/Pilot。
