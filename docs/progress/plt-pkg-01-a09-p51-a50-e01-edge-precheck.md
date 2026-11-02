# PLT-PKG-01-A09-P51-A50-E01：Handover Action 来源导航 hosted Edge 验收（编码前检查）

- 日期：2026-11-02
- 状态：PASS_LIMITED；编码前检查完成；等待执行
- 当前Phase：Phase 2 Platform Core；Gate 3 BLOCKED
- 当前WBS：PLT-PKG-01-A09-P51-A50-E01
- 输入基线：A50实现及结果、CR-HND-009、冻结HND Action API、固定版本详情和Evidence Viewer权限合同
- 前置任务：A50后端/前端实现与 hosted run 41391544470全量自动化通过
- 涉及模块：Windows hosted Edge合成验收 harness、Handover Action与固定版本详情路由
- 涉及实体：合成 Project/Session/Action/Analysis/Version/Item/Document/Evidence
- 涉及API：本地合成 Action GET和 source-location GET；固定版本只读GET。测试不得调用外部客户服务或真实AI provider。
- 涉及权限：只用合成身份、合成Project和隔离runner临时数据；API响应由同源fixture/mock服务提供，验证客户端不接受任意外链、跨Project和失效引用。
- 验收标准：云端Windows Server runner上的Edge真实浏览器可从Action进入固定版本的准确问题卡并滚动定位；HUMAN来源显示不可用且不生成链接；越权/跨Project/失效来源拒绝并保留Action状态；分页定位及返回/重载路径确定；报告明确标记合成身份、托管Server 2025，不推定Win11设备兼容。
- 风险：把常规A17 PlanVersion Edge流程误作A50证据；隔离要求以独立A50断言和机器可读summary规避。
- 回滚：移除专用validation harness、workflow job和合成fixture；不改变产品代码/数据库或业务数据。
- 预计修改文件：新增 `validation/hnd-action-source-location-edge/` harness/fixture/readme；更新 `.github/workflows/cloud-sandbox-validation.yml` 增加隔离job；新增本任务结果记录并更新STATUS/CHANGELOG/CR-HND-009。
- 风险控制：所有运行仅由GitHub Hosted Windows runner执行，仓库与临时文件位于D盘runner工作区；禁止用户本机运行、客户数据、秘密、真实凭据、生产服务及正式License trust。
- 验收后状态：仅可关闭A50浏览器专项证据；不改变Gate 3、Pilot、正式Release及三平台状态。


## 验收结果（2026-11-02）

- 最终GitHub hosted run：[41396427656](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41396427656)，全13 jobs成功；Edge专项job上传合成证据Artifact。
- Edge四场景：Analysis Action跳到固定版本并跨页定位准确问题；HUMAN无定位控件/来源API调用；跨项目目标拒绝且Action状态不变；不存在/过期来源失败关闭且详情不丢失。
- 同run后端3,850项、前端2,075项/200文件、typecheck/build、父包候选20,122文件、PG18.6/pgvector0.8.6、A34和A17检查通过。
- 结果PASS_LIMITED；仅GitHub托管Windows Server 2025/D盘临时环境和合成数据；无外部API、客户资料、本机/C盘程序运行或正式License信任。不得据此推定Windows11设备、Gate 3、Pilot或Release通过。
- 实施/验收夹具偏差和逐轮修复已记录于CR-HND-009；最终浏览器结果机器摘要：`source_location_requests=3`、`fixed_item_pages=2`。
- 下一步：依STATUS.md，从Gate 3审计记录的Prototype真实业务Owner缺口中确定一个单问题WBS并进行编码前检查。
