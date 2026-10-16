# SUR-06-A02：通用 Checklist 资格合同、注册表与 Handover adapter

日期：2026-10-07。结论：`SUR_06_A02_WORKFLOW_QUALIFICATION_REGISTRY_PASS`。下一项：
`SUR-06-A03` Survey 两项 current-fact policy、Repository 与 Owner。

## 实现结果

- 新增业务中立的 `CurrentChecklistQualificationQuery/Qualification`、Evidence/Review 观察值及严格
  结构校验；结果固定 project/stage/item、业务 subject identity/version、内容指纹、非空 Evidence、
  APPROVED ReviewRound，并提供四元 coherence key。
- 新增显式、只读 item-key 注册表；拒绝空注册、重复 key、未知 key、错 Project/stage/item、Owner
  错类型与异常泄漏，不做动态 import、插件发现或默认 Owner。
- 新增 Handover compatibility adapter，把已验收 Handover Owner 结果逐字段映射到通用合同；不修改
  原 Handover policy、Repository、record/preview/transition service、HTTP 投影或 Windows 组合。

## 兼容、迁移与回滚

- 本项是 A04 接线前的内部增量，无 Schema/Migration、公开 API、依赖、Secret、License 或数据外发变化。
- 通用模块当前未注入生产服务，运行行为保持不变；删除两个模块及专项测试即可回滚。
- 当前不声称 Survey Owner、Checklist、Stage Transition、Windows PG、Edge、Gate 3、UAT 或发行通过。

## 验证证据

- 新增专项 6 项通过；既有 Handover policy/Owner、qualification preview、Checklist record、Transition
  定向 37 项通过。
- 后端全量 2948 项通过、3 项环境跳过；`compileall` 通过。
- 开发 wheel 1107 entries，包含通用合同与 Handover adapter；SHA-256：
  `35d195f6210f1f1baa8b109325e51469f001e9348921338f72b8b70abb5b858c`。
