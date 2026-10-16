# SOL-03-A05-A03-P05-P01：OutlineVersion 历史读取前端客户端

日期：2026-10-09。结果：`SOL_03_A05_A03_P05_P01_OUTLINE_VERSION_READ_CLIENT_PASS`；仅客户端合同，页面/浏览器未验。

编码前检查：Phase 2；输入为 Gate2 API-04、A05-A03-P02 增量投影与 P03/P04 真实后端，前置满足。仅 Solution 前端 API 客户端与单元测试；不变更 Schema/Migration、后端路由、角色或冻结 API。验收为真实路径、same-origin/no-store、严格响应/身份/计数/分页校验、已知错误安全映射及畸形数据失败关闭。风险为将历史固定引用误解为当前资格，因此模型/命名明确为历史读取，不复用候选提交对象。

新增 `OutlineVersionReadClient` 的 LIST/GET，严格核对项目/目录/版本身份、版本号倒序、连续游标边界、SHA-256 摘要、计数与详情固定引用一致性；不接受 ETag 或非 no-store 响应。缺 Session、License、资源不可见分别映射安全提示，其余网络/服务异常统一失败关闭。单元定向 4 项通过；前端全量 125 文件/1720 项、类型检查和生产构建通过。构建有既有主 chunk 大于 500 kB 的非阻断提示，未将其报告为性能验收。

回滚可撤客户端及测试，不触碰历史数据。下一项 P05-P02 列表/详情页面；之后浏览器/PG 复验。GLOBAL 项目候选发布继续按 CR-SOL-018 独立实施，Gate3/发行仍 BLOCKED。

TraceLink：Gate2 API-04 → A05-A03-P02/P03/P04 → 本客户端 → P05-P02 页面/浏览器。
