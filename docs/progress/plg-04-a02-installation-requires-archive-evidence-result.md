# PLG-04-A02：Installation Owner 归档证据复验结果

- 日期：2026-11-06
- 结论：PASS_SCOPE_LIMITED
- Change Request：`docs/changes/CR-PLG-016-installation-requires-archive-evidence.md`
- 验收运行：[GitHub Actions 42092840314](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42092840314)
- 执行位置：GitHub hosted Windows Server 2025 runner 的 D: 临时目录；未在用户本机或 C: 盘运行。

## 实现与验收范围

`PluginInstallationOwner` 在读取不可变 Package 事实后，先要求只读归档 Port 对精确 PackageId、PluginId、Version、SHA-256、签名、Manifest 与登记快照重新验证，再调用独立 Host 安装/兼容证据。归档仅证明登记包内容完整，不替代Host安装事实。任一步失败均不记录 Installation、RuntimeValidation 或 Audit。

本项没有增加 Schema/Migration/API，未改默认生产装配或正式publisher trust；未解压、安装、启动或执行插件。Hosted 合成 PG18 使用受控测试签名和合成Host证据，不构成正式信任或真实主机安装。

## 结果

- 后端全量测试与 wheel、前端测试与生产构建、PG18/pgvector sidecar、嵌入式运行时和非发行父包构建通过。
- clean parent PG18 生命周期 smoke、A35候选交接、A34包替换与显式手动恢复演练、P24/A50通过。
- A17 packaged Edge/HTTPS/PG job成功；A17结构化 summary marker 列表含 `PLG_04_A02_PG18_PASS`。PG18专项执行了：
  - 有效签名归档与独立合成Host安装证据通过，Installation、RuntimeValidation、Audit事实按Owner持久化。
  - 损坏归档在Host evidence查询前拒绝；零Installation/RuntimeValidation/Audit事实。
  - 签名失配在Host evidence查询前拒绝；零Installation/RuntimeValidation/Audit事实。
  - 有效归档但Host evidence缺失时拒绝；零Installation/RuntimeValidation/Audit事实。
- 本项结论仅PASS_SCOPE_LIMITED；Pilot、Gate 3与正式Release仍未通过。

## 独立阻塞

同一workflow的P25 real Output Create HTTP/Edge job仍在创建数据库目录前由 `initdb.exe` 返回 `3221225781 (0xC0000135)`，没有标准输出/错误输出，未启动真实HTTP/Edge。此为已有独立托管环境诊断（CR-OUT-021），不改变A02专项结果，但workflow整体非全绿。

## 偏差与追溯

测试夹具旧接口、A06验证器缺少归档Port及临时归档生命周期过短、A17嵌套输出marker丢失，以及A05结构化返回对象缺少预设markers字段，均已先记录于CR-PLG-016后修复并重新托管验收。最终A17 summary明确包含A02 marker；未以直接stdout或未传播的子回调输出来代替结构化证据。
