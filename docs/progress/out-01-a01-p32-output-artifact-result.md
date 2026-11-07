# OUT-01-A01-P32 验收结果：OutputArtifact 持久化基础

- 日期：2026-11-05
- 结论：PASS_SCOPE_LIMITED
- 变更记录：[CR-OUT-028](../changes/CR-OUT-028-output-artifact-persistence.md)
- GitHub hosted run：[41988323089](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41988323089)
- 执行环境：GitHub hosted Windows Server 2025 runner，项目工作区及临时 PostgreSQL 均位于 runner D: 临时目录；未在用户本机或 C: 运行代码。

## 验收证据

- Migration 0232 在空库及既有合成数据上升级成功；空库降级后重升成功；存在 Artifact/Validation 历史时降级被拒绝且历史保留。
- 项目、OutputRequest、输出类型、PluginExecution、GENERATED_ARTIFACT Document、DocumentVersion 与 FileObject 的复合候选键/FK 约束存在并阻断错绑。
- Owner 生产写保持关闭；不可用 AVAILABLE 状态被拒绝；四项受控 validation code 全部 PASSED 后合成 AVAILABLE 正例成功。
- Artifact 引用不可变、validation result 只允许追加，根/子表 TRUNCATE 均被阻断；validation child fixture 数为 4。
- 同 run 后端测试/wheel、前端测试/typecheck/build、父包 PostgreSQL 18 smoke、A17 与 A34 均成功。
- 父包内部 SHA-256：`ad37ffd0b7fc6b59968ecb2b10f2e8cddc9f3431c9851e70a0e03c221d1440e2`；payload 文件数：20,216。

## 运行边界与未通过项

P25 的独立 Windows Edge + HTTP 检查仍失败：托管 Windows runner 上 `initdb.exe` 退出码 `3221225781 / 0xC0000135`，PostgreSQL 数据目录未创建，因此未启动真实 API/Edge，不能由 P32 的父包 PG smoke 推定 P25 通过。P25 保持 `BLOCKED_DIAGNOSTIC`，整体 workflow 结论为 failure。

本结论只覆盖 P32 的 Schema、约束、写关闭和 PostgreSQL 生命周期。未创建文件正文、未运行插件/Worker、未执行生产发布；不代表 P25、Windows 11 设备、Pilot、Gate 3 或正式 Release 通过。P33 前置方向为受控输出成功终结 Owner，需继续保持默认组合未接入和无真实文件/插件副作用。
