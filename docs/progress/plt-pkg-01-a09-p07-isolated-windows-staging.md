# PLT-PKG-01-A09-P07：Windows统一候选隔离暂存演练

日期：2026-10-01；状态：`NON_RELEASE_STAGING_INTERNAL_PASS / INSTALL_NOT_AUTHORIZED`。

## 编码前检查

- 当前Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P07`。输入基线：Gate 2冻结，A09-P02固定SHA的非发行统一候选，A09-P04 ASCII安装根规则，A09-P06只读安装计划；前置任务可用。
- 涉及模块：新独立暂存工具 `tools/stage_windows_unified_candidate.py` 和测试；实体/API/权限/Migration：无。正式安装器、SCM服务与数据库不调用。
- 验收标准：源ZIP全量Hash及非发行身份先验证；仅允许系统Temp目录的全新ASCII直系子目录，不能触碰`C:\PLMTool`；暂存时逐件Hash、落盘后全文件集/逐件Hash，结束后再次确认源ZIP身份；结果始终`installation_performed=false`、`install_authorized=false`、`release_eligible=false`。坏源/坏路径/重复目标/中途源变化失败关闭。
- 风险与回滚：约1GB本机临时磁盘占用，失败现场保留供排查而不自动递归删除；独立临时目录可在核对后清理，旧ZIP及用户数据不改。暂存不能代表正式安装、License、ACL或法律验收。

## Windows11执行证据

- 源：`artifacts/package-prep/windows11/unified-candidate-fe9b2516b150/NOT-FOR-RELEASE-windows11-unified-candidate.zip`，SHA-256 `da285e1c88d45f195d141f5eb6cba5f887f019063f4547a0a54ecae78c251bff`。
- 目标：`C:/Users/17231/AppData/Local/Temp/plm-unified-stage-20261001a07`，执行前确认不存在；只允许Temp下受命名规则约束的新目录，复制前全量检查ZIP。
- 结果：`NON_RELEASE_STAGING_PASS`；19,449件载荷写入时Hash与清单一致，落盘后重新读盘逐件Hash及完整文件集一致；附加3个清单文件总计19,452个文件，约1,067,075,345字节。最终结果明确`installation_performed=false`、`install_authorized=false`、`release_eligible=false`。
- 新增源ZIP末次Hash复核以防两次打开之间源文件变化；合成正例与模拟源变化拒绝、坏源复制前拒绝、目标路径拒绝合计单元4/4通过。`C:\PLMTool`仍不存在，三项固定PLM服务未安装；未运行Migration。未执行正式账户/Server2025/Debian13、真实客户质量或法律发行验收。

本项仅完成隔离暂存。下一项建议优先完善第三方NOTICE/对应源码缺口及 PostgreSQL18/pgvector 的离线交付输入，以推进真正可安装程序；任何正式安装步骤仍需独立前置和客观Gate。`release_eligible=false`。
