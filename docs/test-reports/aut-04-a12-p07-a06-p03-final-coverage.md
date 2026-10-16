# P07-A06-P03 五实际链统一覆盖

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/coverage7.13.5；输入56c5533，Schema0049与生产源码未改。

完整1470unit/contract无失败/errors0/2既有符号链接权限跳过；同轮五实际入口全部通过：reset历史+atomic、change历史+atomic、Windows reset、Windows change、新current-final八故障与两个正常提交控制；保原发布回归。内部合成信任不代表正式发行材料。

|完整范围|行|分支|结论|
|---|---|---|---|
|原21密码文件含SCRYPT/进程预算|1007/1017，99.017%|321/370，86.757%|未达90%分支|
|完整Auth|3095/3334，92.831%|744/974，76.386%|未达90%分支|
|完整Windows工厂单列|362/369，98.103%|8/10，80%|未完整覆盖|

exit1为门槛未达，不是功能失败。密码综合95.746%不替代分支90%；没有改分母、增加排除或降低标准。测量本机实际CTracer（另进程同默认配置读取collector确认），未更换测量core。

新独立raw `.poc-runtime/auth-security-final-fault-coverage/coverage.json` SHA256 `d45e9dd3b2da36c3ebbd771ee18b465ed4205ff79ef81e5544087021a54d39fb`；前轮adapter-defensive JSON/Hash45c4d14a…及更早历史保持。运行日志/raw不提交，只有安全计数/用例/验证入口进入Git。wheel/性能/生产升级未跑，无生产/Migration/API/权限/算法/依赖变更，兼容0049，无升级需求。

剩余测量缺口：change Service14个异常处理关联边；reset Service非规范secret拒绝行91及8个边；Access类型/result坐标、before-flag与current-source错误；Repo条件更新/Session撤销返回异常；Result BEFORE/AFTER来源与记录后读取失败；issue未找到Credential；Proof/Replay构造边。已有相关拒绝用例与报告不一定一一对应，不能仅凭报告将边判断为不可达、工具误差或生产缺陷。

下一A07先逐边证据审计（现有用例→实际路径→测量边），必要时做独立最小复现，再按真实缺口补测；完整Auth其他文件缺口也保留，不能只以密码范围关闭全部Auth。90%/性能CR008 OPEN/FAIL/默认4、正式trust/目标环境/UI/安装升级/UAT/Gate3及可用程序包未完成。
