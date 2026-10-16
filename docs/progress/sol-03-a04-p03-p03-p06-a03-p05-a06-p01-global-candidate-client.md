# SOL-03-A04-P03-P03-P06-A03-P05-A06-P01：项目 GLOBAL 候选安全读取客户端

日期：2026-10-09。结果：前端读取合同与全量测试、类型检查和构建通过；尚未接入创建页或完成浏览器验证。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate 2 API-04、CR-SOL-018、DEC-1157、已验 A04/A05 独立项目 GET 与 Windows 组合。
- 单一问题：为项目 PM/IM 页面建立不复用管理员 GLOBAL 列表的最小候选安全读取桥。
- 模块/实体/API/权限：仅前端 Solution API 客户端；服务端现有项目候选 GET，不改数据库、后端 API、角色或依赖。
- 验收：同源/no-store/不跟随重定向；严格五字段与 TraceId、游标格式及空可见页续页；错码匹配与失联失败关闭；前端全量测试/typecheck/build。
- 风险：误用管理员投影泄露原名、空页被误判结束、畸形分页/跨项目响应混入。以独立客户端、字段白名单和严格游标/响应校验控制。项目授权与 CREATE 当前资格仍由服务器重证。

## 实施与验证

新增 `ProjectGlobalReferenceCandidateClient`，只访问 `/api/v1/projects/{projectId}/global-reference-candidates`；返回值只接受根 ID、固定版本 ID、人工审定标签、版本号和 `ELIGIBLE` 五字段，拒绝额外的原始名称或来源字段。客户端接受 `items=[]/has_more=true` 与新签名游标，不把空页视为结束；请求同源、no-store、禁止重定向，响应须 JSON、no-store 且 TraceId 合法。只映射状态匹配的会话/License/项目不可见/归档错误，其他异常封闭为不可用。

定向 4 项通过。首轮 typecheck 报 `version_no` 为 unknown，经数值判定后显式收窄并重跑；前端全量 127 文件/1729 项通过，typecheck/build 通过。该客户端目前未挂页面，也未调用真实浏览器/PG；不宣称 P06 GLOBAL 选择可用。

兼容/升级/回滚：无 Schema/Migration、后端 API、角色或依赖变化；新增未挂载前端模块，删除该模块即可回滚。后续 P02 在创建页集成多页完整候选、当前项目绑定、选择及原操作恢复，P03 用 Win11 浏览器/隔离 PG 验收。正式服务账户、Server2025、性能、Gate3/发行仍未验；Debian13 实机依用户指令跳过。既有 Vite 大 chunk 提示保留。

TraceLink：Gate 2 API-04 → CR-SOL-018 → DEC-1155～1157 → A04 项目 GET → A05 Windows 组合 → 本客户端 → P02 页面 → P03 浏览器。
