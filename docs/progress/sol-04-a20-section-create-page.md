# SOL-04-A20：Section 创建页与父目录入口

日期：2026-10-09。结果：`SOL_04_A20_SECTION_CREATE_PAGE_PASS`；前端合同通过，真实浏览器/PG 待 A21。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A20。
- 输入基线：Gate 2 API-04、A17 Outline/Section 读链、A19 安全 CREATE 客户端、A16 拆分；前置满足。
- 模块/实体/API/权限：Solution 创建页、Outline 详情入口与 Router；Section 初态与同项目活动 Outline，冻结 API/Schema 无变。仅当前项目 PM/实施成员可提交，后端最终复验。
- 验收：直接访问创建路由仍重新读取父 Outline；跨项目/已归档/不匹配父项不提交；原 Key 会话保存、结果不明显式同 Key 重试、成功跳 Section 详情；页面与前端全量/typecheck/build。
- 风险：路由参数伪造、存储损坏、结果不明换 Key 或把初态章节当正文/签署。

## 实施与验证

新增 `/projects/:projectId/solution-outlines/:outlineId/sections/new` 与创建页；Outline 详情仅在活动目录、当前写角色时显示入口。创建页即使被直接访问也须重新从后端读取并核对父目录项目/ID/活动状态。规范化章节键后，按用户/项目/父目录范围把原载荷和 Idempotency-Key 写入浏览器会话；未知结果保留键并要求用户显式确认同键重试，存储不可读/不可写时停止提交。页面注明仅创建逻辑身份，不代表正文、评审或客户确认。

首轮定向测试发现成功跳转时旧页面尚未卸载，返回父目录链接在新路由瞬间丢失 `outlineId`，产生 4 个未处理路由异常；改为稳定父目录链接参数并停止离开创建路由后的重新读取。复跑定向 `7 passed`、无未处理异常；前端全量 `117 files, 1681 passed`；`pnpm --dir apps/frontend build` 含 typecheck/build，退出 0。真实浏览器/PG 未运行，正式目标账户与 20 并发仍待。

兼容/升级/回滚：无 Schema/Migration、依赖、冻结 API 或服务端权限变化；撤下创建页/路由/入口可回滚，已创建 Section 不删除。下一项 `SOL-04-A21` Win11 隔离 PG/真实 Session 浏览器读写链；Server2025/正式信任源/性能与 Gate3/发行另验。TraceLink：Gate 2/API-04 → A19 → A20 → A21。
