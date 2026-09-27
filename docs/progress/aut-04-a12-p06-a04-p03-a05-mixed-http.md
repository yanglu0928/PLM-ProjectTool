# AUT-04-A12-P06-A04-P03-A05：实际Windows混合HTTP

2026-09-27；版本0.1.0.dev0；状态FUNCTIONAL_PASS / PERFORMANCE_FAIL。上一轮完成配置/工厂装配并推送7ecf5c4，属于实际进展。

编码前检查：Phase2；WBS本项；输入冻结64cdf09/0049/CR-AUT008/A04装配与固定KDF。前置满足；仅独立验证脚本/证据，无实体、API、权限、生产实现变化。合成信任与临时PG18、真实Windows写工厂/Scrypt，10个独立reset与10个本人change同时请求；新写各原结果/凭据2/旧Session失效，历史换成真实当前Session后原Key/原密码重放，九表全量不变。

验收：每批30个真实KDF，总峰值<=配置slots、结束0；20响应全部200，无SQL错误。报告原普通写20并发P95<=1000ms，不因功能通过掩盖性能失败；运行退出码对应完整指标。配置通过实际Bootstrap输入，独立进程支持4/8/16，不能替换legacy gate虚报真实容量。

风险：混合共享4排队、线程池/数据库池竞争及内存影响，不降低算法/放宽标准/无限重试；正向信任合成、不涉及客户数据外发或正式生产；无Migration/生产升级，回滚仅撤验证脚本不删历史。正式trust/目标账户/平台/覆盖率/Gate3/可用安装包仍待。

首次16脚本在外层fixture先构造默认4后被真实唯一预算正确拒绝，未进入混合测量，不是16性能证据。已修验证入口，整个独立进程从首个factory开始使用同一PLM_PASSWORD_KDF_SLOTS；没有重置或替换生产gate。4实测两批各20成功/30真实KDF/peak4/end0/SQL0，fresh P95 2199.128ms、history2507.062ms；九表原结果与旧Session/原回归通过，exit1性能FAIL。16修复后测量待。

修复后16独立进程实际结果：fresh/history各20成功、30真实KDF、共享总峰值16、结束0、SQL错误0；fresh P95 1218.475ms仍FAIL，history999.713ms单轮PASS。九表历史全量不变、原首次数据/reset ETag保持、旧Session失效、Windows状态与发布回归通过；脚本最终exit1整体性能FAIL。P95按原始精度判定，打印保留三位小数；单轮临界通过不足以证明持续负载或全部Auth性能。

没有生产代码/Migration/API/依赖变化；默认4不改，没有部署或外发数据。测试数引用A04既有1430无失败/2跳过，本轮不声称重跑unit/wheel。当前验证脚本支持真正配置4/8/16，但本轮8未运行，不虚报。下一A06迁移旧五组cost profiler：真实Bootstrap从首个factory绑定同一预算、计时代理不得另建容量；固定算法/1秒标准保持，不无限增加slots。Gate3/完整包未完成。
