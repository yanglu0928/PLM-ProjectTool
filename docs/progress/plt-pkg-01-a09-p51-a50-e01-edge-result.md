# PLT-PKG-01-A09-P51-A50-E01：托管 Edge 待办来源导航验收

- 日期：2026-11-02
- 状态：PASS_LIMITED
- 关联变更：CR-HND-009
- GitHub Actions：[run 41396427656](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41396427656)（13/13 jobs success）
- 分支提交：`bfb94cfa0a401b391793e01cbd15200bd2a46073`

## 验收范围

在GitHub hosted Windows Server 2025的Microsoft Edge headless中，使用同源HTTP模拟服务、同run的Vite生产构建及完全合成身份/数据，执行真实浏览器交互。仓库、临时浏览器配置、服务和数据均在D盘runner temp；没有在用户本机/C盘运行代码，无客户资料、外部API或正式License信任。

## 结果

|场景|结果|证据|
|---|---|---|
|Analysis来源待办|通过|按需请求source-location，跳转固定Analysis Version；第1页200条后翻页，在第2页定位目标Item并调用滚动|
|HUMAN来源|通过|显示人工来源说明；无来源定位按钮、无source-location请求|
|跨项目来源|通过|目标Project不匹配时拒绝链接；原Action详情和SUBMITTED状态保留|
|失效/过期来源|通过|来源解析返回受控不存在；不生成链接，原Action详情和状态保留|

机器摘要：`checks=4`，`source_location_requests=3`，`fixed_item_pages=2`，`customer_data=false`，`external_api_calls=0`，`formal_license_trust=false`，`release_eligible=false`。

## 同run回归与包证据

- Backend：3,850 tests及Wheel build成功。
- Frontend：200个测试文件、2,075项测试通过；typecheck和production build成功。
- 同run Windows父包候选：SHA-256 `238d6a53db0f5e7e9955020e6caeecbb5a8d445a0f2025eadca081638ff83237`，20,122 payload files；临时PG18.6/pgvector0.8.6 lifecycle通过。
- A34隔离包替换/失败候选隔离/手动恢复及A17 Packaged PlanVersion Edge/HTTPS/PG（29次API）通过。A17仅为既有PlanVersion流，不应当作A50专项证据；A50专项证据来自本WBS Edge job。
- 专项Artifact：`plm-a50-edge-source-navigation-70ad67d35c4e0e4149f479970e2cb2a0f5cb27c3`，上传并留存在该Actions run。

## 限制与后续

PASS_LIMITED仅说明这一托管Server 2025合成浏览器验收及同run自动回归成功。未进行Windows11实机运行/安装，未启动正式产品服务，未建立正式License信任；Gate 3、Pilot、正式Release仍NOT_READY。下一任务按STATUS.md从Gate 3审计记录的Prototype真实业务Owner缺口中确定单一WBS并完成编码前检查，不将合成状态升级为正式业务事实。
