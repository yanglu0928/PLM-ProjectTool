# AUT-04-A12-P07-A07-P01 异常分支测量审计

2026-09-27；Phase2；LOCAL_REPRODUCTION_PASS。输入c004980/冻结64cdf09/Schema0049；前置A06真实五链通过但覆盖未达。只审计Auth异常路径测量，不修改生产/API/实体/权限/Schema/依赖。

验收：选取已有change source类型拒绝用例，在独立coverage与独立Python line/exception trace中运行并核对具体边；合成最小compact/expanded函数AST等价、两种输入一致后分别测量。输出只安全坐标/计数/结果；不覆盖旧raw JSON。不能从单例推广全部缺口，不改范围/pragma/门槛，不将实验当权限/PG验收。

风险/回滚：内部测量API可能因工具升级变化，固定本机7.13.5/3.13.15；保存验证入口和独立原始证据。撤审计入口无生产升级。只有复现证据充分才能决定格式或测量调整；90%/性能CR008 FAIL/默认4/正式trust/Gate/包待。

结果：既有source类型拒绝用例两次guard83异常，实际coverage记录83→75事务上下文退出、仍列83→162未覆；独立with最小例compact记录13→12退出却列13→15未覆，AST等价expanded不列该guard缺口，两种输入行为一致。无with与只有retry/finally对照未出现该缺口，未从单例推广全部缺边。exit0，Hash/明细见test-report。完整unit/五PG/全量coverage/wheel本批未重跑，原86.757%保持；下一P02仅两Service同模式排版分行、AST等价与完整unit/五PG/同范围覆盖复验，不改排除/门槛或豁免真实缺口。
