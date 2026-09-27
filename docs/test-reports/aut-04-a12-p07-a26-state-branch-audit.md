# P07-A26 用户状态逐边结果

2026-09-27 Windows11/Python3.13.15/coverage7.13.5。完整1525unit/contract21.837秒、失败0、错误0、既有跳过2，exit0。新增1参数化方法覆盖ActorProof.user_view的None/object/string拒绝，Service noCommit/UOW退出/不reserve通过。

五方法分别coverage与独立trace两轮5/5通过。guard42异常3次，真实42→50已覆盖（新行为测试）；101/111/116/127异常1/1/8/1次，其到139坐标仍缺。101/111/127实际拒绝到UOW出口100，116实际到raise120。116为多行条件且raise同最后条件行，不能笼统认定五条都是单行测量问题。

独立runtime auth-security-state-branch-audit JSON SHA256 `e0a7580b90bb998fcf9c54d8c0e9cabc471d2be2c78a00dd83f0f9d4be502a79`；A21原raw重验`18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22`未变。原始诊断/本地产物不上传。只收行号/事件，无秘密/私有消息。

Port合同，不冒充实际SQL。生产/Migration/API/权限/依赖未变，无升级要求，可撤测试。完整15链coverage、性能、wheel未跑，完整Auth新百分比不推算，完整安全/CR008性能FAIL/trust/Gate/可用包待。追溯DEC-20260927-374及同名progress/validation；下一仅其余四guard等价布局及真实状态final来源验收。
