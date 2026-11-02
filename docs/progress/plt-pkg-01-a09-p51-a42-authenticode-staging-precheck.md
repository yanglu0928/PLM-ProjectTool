# PLT-PKG-01-A09-P51-A42：暂存CLI接入包外签名校验（编码前检查）

- 日期：2026-11-02
- 状态：编码前检查完成；CR-PKG-013 的 A42 接入范围已先行记录。

当前Phase：Phase 2 Platform Core；Gate 3 未通过。
当前WBS：PLT-PKG-01-A09-P51-A42。
输入基线：CR-PKG-012、CR-PKG-013；A40暂存CLI；A41 Authenticode验证器。
前置任务：A41 PASS_LIMITED；真实产品发布者指纹仍未提供。
涉及模块：`tools/stage_windows_parent_candidate_offline.py` 及验证器；仅在提供外部安装文件时进行签名检查。
涉及实体：候选ZIP及外部摘要、可选独立安装器文件、包外签发者Thumbprint、固定暂存回执。
涉及API/数据库：无。
涉及权限：只读ZIP、摘要及安装器签名；写入仅限新建非C RUNNER_TEMP目标；不运行安装器、不改证书存储、不联网、不连接服务/数据库、不读取密钥。
验收标准：安装器与指纹参数必须成对出现；提供安装器时必须在ZIP暂存前验签。无效签名或错误pin时不调用ZIP暂存器且目标目录不存在；有效hosted签名+匹配pin时可暂存，回执仅标记TEST_ONLY且installation_performed=false。没有真实发布者证书时不得声称生产信任。GitHub hosted Windows 2025验收，不在本机运行，不推定Windows 11。
风险：回执可能被误读为正式信任；必须保留TEST_ONLY标签和各发行状态false。回滚：恢复旧CLI接口并删除对应测试；无Schema/API/安装目录迁移。
