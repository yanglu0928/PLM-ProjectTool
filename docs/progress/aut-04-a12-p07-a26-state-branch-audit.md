# P07-A26 用户状态异常路径核查

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A26；输入冻结64cdf09/0049、A21原raw及现有UserState。核查五个异常坐标42→50、101/111/116/127→139；先比对已有测试，发现ActorProof.user_view错误类型尚无直接拒绝测试，补该单一合同并核对其余四边实际trace/coverage。不改生产/API/权限/Schema/依赖。

验收：新增ActorProof当前用户View类型异常参数化用例，Service拒绝/noCommit/UOW退出/不reserve；五个guard独立coverage与trace实际异常证据，完整unit/contract实跑。保raw/90%，不把新增真实测试和布局统计混为一谈。风险/回滚：仅Port测试，不冒充SQL；新runtime保旧raw，无升级，完整15链coverage/性能/wheel另项，Gate/包待。

结果：新增1方法三种非法View，完整1525unit/contract21.837秒、失败0/错误0/既有跳过2，exit0。五方法独立coverage/trace两轮5/5通过。guard42新增拒绝3次、42→50已覆盖；其余101/111/116/127拒绝1/1/8/1次，而到139坐标仍缺。116是多行条件、raise在120，与单行布局不完全相同，后续必须逐节点验证，不泛化。

新raw SHA256 e0a7580b90bb998fcf9c54d8c0e9cabc471d2be2c78a00dd83f0f9d4be502a79；A21旧raw18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22未变。无生产变更，完整15链coverage/性能/wheel未跑，完整Auth不推算。下一A27仅其余四guard等价分行/完整unit/真实状态final来源链验证；Gate/包待。
