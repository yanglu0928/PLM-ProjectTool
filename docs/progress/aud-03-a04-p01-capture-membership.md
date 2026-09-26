# AUD-03-A04-P01：固定成员摘要与Schema变更记录

日期2026-09-26；版本0.1.0.dev0；Phase2；结果DOMAIN_CONTRACT_PASS，Schema/真实capture尚未实施。

## 编码前检查与Changed / Files

WBS限定一个问题：固定来源集合规范及其完整性摘要。输入冻结API-02/API-03、A01设计、A03导出Spec、实际0005审计追加约束与head0036；前置满足。涉及Audit owned成员坐标，不改权限/公开API/其他模块。实施前CR-AUD-001记录新增三表的差异、首个成功集合不可替换、源关联/封口/并发/迁移拒绝丢历史验证要求；实际SQL设计在P02进一步收敛后实施，不以本条冒充0037。

新增domain/capture_membership.py与8项unit；CaptureMember只持event UUID/time，冻结且每次摘要再验。CAPTURE-MEMBERSHIP-V1先写域分隔，再按降序(time,UUID)逐条写规范UUID|UTC微秒Z换行。空集合明确与空字节Hash不同，等价时区一致。拒绝零UUID、无时区、逆序、重复UUID（包括不同时间）、非成员/腐损对象。源迭代异常向外传播，不返回截断成功。无需读取事件正文；重复检测O(n)UUID内存，未声称常量空间/性能达标。

成员摘要不是权限/签名/实际源存在证明、不是数据库MVCC或已封口证明、也不是文件字节Hash。不得将构造成功/测试通过用于正式导出放行。真实来源必须后续由数据库单次选择及不变/封口机制确定，再由真实Owner权限及Worker租约校验。无Session、Token、自由正文、路径或客户资料写入。

## Tests / Result / Migration / API / Compatibility

Windows11/Python3.13后端813项无失败，2项既有符号链接环境跳过。新增8项实际验证空集域向量、显式规范字节向量、生成器、时区等价、UUID/time全绑定、排序及两类重复、异常坐标、冻结/腐损再验及源故障不截断。未运行新真实数据库capture、并发/权限、HTTP或文件导出验证。本项无ORM/Migration/API/角色/依赖变化，无数据升级动作；可回退未装配纯合同代码，历史不变。

开发wheel构建PASS，SHA-256：`4b6215504fde7eaf2f3fea19a0475fc8fae1a57c94c4cb944d412247dbdd9267`，不是正式安装包。CR仅实施前计划，0037未创建/执行。Server2025未验，Debian13暂不验证，目标保留。Gate3/完整业务Owner/真实质量/正式账户材料/性能/UAT与可用程序包仍未完成。

## Next

AUD-03-A04-P02：收敛CR-AUD-001三表实际SQL、ORM和0037，明确提交完整性/封口后禁止追加/源归属/锁序/down保护，真实空库及旧数据up/down/re-up与并发验收；然后P03实际capture。POST仍关闭。
