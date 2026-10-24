# 原生 OCR 通知候选清洁解包

日期：2026-10-01；WBS：`PLT-PKG-01-A09-P45-A04`；状态：`NON_RELEASE_NATIVE_OCR_NOTICE_CLEAN_EXTRACT_PASS`。

固定新候选 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，解包前后均重新核对 P43/P33/P22 谱系、34 项 PE 矩阵和新 ZIP 全量清单。目标为全新直接 ASCII Temp 子目录 `plm-native-ocr-stage-20261001b`，不触及正式安装根、服务或数据库。实际载荷 21,158 项加 3 项元数据，逐件 Hash/文件全集读回通过；61 条映射逐条指向已解包的 42 份正文，正文再次计算 SHA-256，审阅标志与发行标志均保持 false。真实命令退出 0。

第一次执行在文件写入前因暂存脚本将哈希清单名归一化大小写后与 ZIP 原名集合直接比较而失败；独立集合检查确认 ZIP 为 21,158 项载荷＋3 元数据、无缺漏。修复为保留原名用于全集比较、仅用大小写折叠集合检查重复，在**另一全新目录**重跑通过。首次目录未创建，不影响历史候选。定向单元 2/2；旧通用解包验证器仅增本候选 kind，不改变旧候选行为。

本项仅是隔离文件完整性检查，不等于安装、法律批准、产品最终 LICENSE/NOTICE 或 Gate 验收。`release_eligible=false`、`legal_clearance=false`、`installation_performed=false`、`services_changed=false`、`database_started=false`。后续在独立布局检查包内运行链与通知可检索性；正式信任源、Server 2025 和 Gate/UAT 仍待。
