# AUT-04-A12 重置密码前置调查

2026-09-27 / 0.1.0.dev0 / PRECONDITION_GAP_CONFIRMED。

Phase2，Gate3未通过；输入冻结DM02/API02、当前Windows状态链1e99787。涉及Auth User/PasswordCredential/Session和冻结reset/change，不实施生产密码写入。调查范围：临时密码强制改密实际执行、会话授权边界、首次结果/幂等重放。风险：未落实标志即可完整管理；旧首次结果无法证明reset/change密码载荷。

## 实际证据与结果

- 全仓库查源确认must_change_password仅存储，密码签发、当前Session和原Admin proof未读取；reset/change Service/HTTP缺失。
- 新验证在独有临时PG18库追加Credential2（must_change=true），原Credential1保留，显式TEST_ONLY Admin角色夹具；真实Scrypt新密码签发Session/current-CSRF/原Admin授权均成功，确认缺口。验证脚本正常退出表示复现成功，不是安全PASS。
- 原双Scope文件发布回归通过；本轮未重跑全unit，1344/2既有跳过为上一P05历史证据，不外推未来修复。
- 按持续授权建立CR-AUT007，选择受限改密Session/实时Credential事实/全业务权限拒绝，先改密再开放reset，严密原密码与新密码的历史幂等一致性。无本轮生产代码/Schema/依赖/安装升级动作；所有临时资料不上传。

下一AUT-04-A12-P01：当前强制改密事实与受限Session授权核心及实际业务Port拒绝矩阵。生产前再次做编码前检查；不能用拒绝临时密码而无改密路径替代完整功能。正式信任/性能/三平台/UI/包/Gate仍待。
