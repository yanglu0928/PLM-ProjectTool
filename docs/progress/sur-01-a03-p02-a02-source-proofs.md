# SUR-01-A03-P02-A02：Survey 类型化来源证明

日期：2026-10-06

状态：`SUR_01_A03_P02_A02_SOURCE_PROOFS_PASS`

Handover、Capability、Project 分别新增 caller-transaction 最小证明 Adapter。它们只返回固定身份与状态，拒绝跨项目、缺失、非当前批准、不可用及停用部门，不暴露正文或路径；Survey 未直连来源私表且本项不写 Survey。

验证：定向1项；Windows 11/PostgreSQL 18.6 正反例通过；后端2786项通过/3项跳过；wheel 1026项，SHA-256 `7530cec86a5b3a58ab69762a96ee09d341ae82231448b9566de2dab72ce3c099`。

下一项：`SUR-01-A03-P02-A03` 完整 DRAFT SurveyVersion 原子创建。
