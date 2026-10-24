# P07-A21 完整安全覆盖结果

日期2026-09-27，Windows 11 / Python 3.13.15 / coverage 7.13.5（仅本地测试依赖）。

完整1524unit/contract无失败、无错误、2既有跳过；原14条实际PG/Windows/Vault验证链和新增A20P02名称来源链均通过。覆盖开始于测试导入前；完整Auth全部文件行3232/3364（96.076%）、分支852/988（86.235%），综合93.842%不能代替分支门槛，ALL_AUTH false/exit1。

原密码21文件1031/1047行（98.472%）、350/384分支（91.146%）本范围通过。Windows完整factory362/369行、8/10分支单列。不得以密码范围通过认定完整安全通过。无文件排除、分母缩减、pragma或门槛调整。

原始JSON保留于忽略的本地runtime auth-security-name-coverage，SHA256 `18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22`。旧A16 JSON重新校验SHA256 `7d6fbfc0499a6a52d01eb844311e78e14a1338e2d87b135d2f91ec34a91e20c3`，未覆盖。原始日志/临时凭据/客户数据不上传。

仍有136条缺失分支。ManagedUserCreate六条、UserRead五条等已覆盖行的异常坐标需要逐边核查，不能套用以往单模式结论；其他真实行为缺口继续补测。生产、Migration、API、依赖未变，性能和wheel未跑，正式trust、CR008性能FAIL、Gate 3与交付仍未完成。追溯DEC-20260927-369及同名progress/validation。
