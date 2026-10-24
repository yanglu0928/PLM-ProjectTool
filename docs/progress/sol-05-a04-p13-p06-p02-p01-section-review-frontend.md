# SOL-05-A04-P13-P06-P02-P01：Section 客户评审待办/详情前端合同

日期：2026-10-23。状态：`FRONTEND_CONTRACT_PASS`；真实浏览器与正式客户操作未验。

## 编码前检查

- 输入：Gate 2 冻结 Review GET/LIST/DECIDE、CR-SOL-024/025、P13-P06-P01 已验 Win11/PG18 合成终态。
- 单一问题：统一评审列表已可列 SOL-05，但详情客户端将主体写死为 SOL-06、页面将所有主体写成“结构化专项”，使 Section 客户评审无法打开和定位固定版本。
- 范围：前端 Review GET 类型/策略配对验证、待办标签、详情主体标签和固定 SectionVersion 链接。不改 API、Schema、权限、License、其他主体页面。
- 权限：前端仅按当前 Session/分配展示决定操作，后端仍为最终授权；旧 SOL-06 行为保留。风险是误将 SOL-05 与 SOL-06 策略交叉配对，通过精确二元校验拒绝。

## 验证

- 前端定向 13 项通过，typecheck 通过；全量 155 文件、1850 测试通过；生产构建通过（存在原有主 bundle 超 500kB 警告）。
- Section 待办标为“方案章节”；详情接受且只接受 `SOL-05/SOLUTION_SECTION_ALL_V1`，展示固定 SectionVersion 导航与客户决定边界提示；SOL-06 保持原路径。
- 未进行真实浏览器/后端联调，本片不把 Vitest 模拟界面标记为 Pilot/UAT。下一项 `SOL-05-A04-P13-P06-P02-P02` 完成 Win11 浏览器 Section 评审待办/详情/决定，以及项目负责人 Section 送审前端入口。

## 兼容与回滚

无数据升级；可回滚该前端主体适配，已存在的 Review/结果不删除。正式客户签署、Gate 3、Pilot、三平台 Release 均未通过。
