# P07-A21 完整安全覆盖复验

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A21；输入冻结64cdf09/0049及A20P02真实名称数据库验证。仅验证脚本，不改生产/API/权限/依赖/统计范围。使用既有完整unit/contract与原14链，加A20P02名称来源链；全部Auth文件分母和行/分支各90%门槛保持，密码21文件与Windows factory单列。

验收：完整测试及15实际链真实执行；新runtime auth-security-name-coverage，保留旧raw及SHA；报告实际覆盖与exit。未达门槛继续未通过，不用组合百分比、删文件或缩scope替代。风险/回滚：仅独立验证脚本与临时库，原fixture清理；撤脚本无升级。性能、wheel、正式trust/Gate/包另项。

实际结果：1524项unit/contract失败0、错误0、跳过2；15实际链全部通过。完整Auth 3232/3364行96.076%、852/988分支86.235%、综合93.842%不替代分支，ALL_AUTH false，exit1。密码1031/1047行98.472%、350/384分支91.146%通过；Windows完整factory362/369行、8/10分支单列。范围/分母/90%未变。

新raw SHA256：18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22。A16旧raw重新校验7d6fbfc0499a6a52d01eb844311e78e14a1338e2d87b135d2f91ec34a91e20c3保持。生产/Migration/API/依赖无变；性能/wheel未运行。下一A22核对ManagedUserCreate六个缺失异常路径坐标与既有故障用例，不无证认定测量误差或不可达；Gate/可用包待。
