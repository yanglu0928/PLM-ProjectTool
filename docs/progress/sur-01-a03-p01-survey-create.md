# SUR-01-A03-P01：Survey identity 创建 Owner

日期：2026-10-06

状态：`SUR_01_A03_P01_SURVEY_CREATE_PASS`

## 完成内容

- 新增内部 `CreateSurvey` 命令、不可变初始视图和 Survey-owned SQLAlchemy Repository。
- 按冻结 `SURVEY_CREATE` 权限允许 ProjectManager 与 ImplementationMember；Customer 角色及归档 Project
  失败关闭。
- 在同一事务中完成当前 Session/CSRF、Project 角色、License、持久幂等、Survey identity、Audit 和
  完成收据；未知结果可用原 Key 精确重放，Payload 改变返回冲突。
- 首次创建固定为 `ACTIVE`、无批准版本、`lock_version=0`、ETag `"v0"`；本项不创建
  SurveyVersion、不开放 HTTP、不导入客户资料。

## 验证结果

- 定向单元测试：9 项通过（包含完整 Project 授权矩阵）。
- Windows 11 / PostgreSQL 18.6：双角色、CSRF/License、客户角色拒绝、并发收敛、冲突、Audit
  故障整笔回滚、零 Version 边界及角色撤销复验通过。
- 后端全量：2785 项通过，3 项按环境条件跳过。
- Wheel：1020 个条目，包含 Survey 创建 Service/Repository；SHA-256
  `3b75760339120d0d0e5dffc8639272db59eb737ef0a9606e1d9d5e5da011c3c6`。

## 下一项

`SUR-01-A03-P02`：实现完整 DRAFT SurveyVersion 创建 Owner；服务端规范化问题、选项、来源和目标部门，
计算内容指纹并在一个事务写入六表。HTTP 仍留待 SUR-05。
