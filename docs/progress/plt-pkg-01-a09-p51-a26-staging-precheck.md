# PLT-PKG-01-A09-P51-A26：隔离候选暂存流程编码前检查

- 日期：2026-10-28
- 当前Phase：Phase 2 Platform Core；CR-EXEC-002 Windows 11内部试用包优先关键路径
- 当前WBS：PLT-PKG-01-A09-P51-A26
- 前置：A24 Web loopback PASS_LIMITED；A25启动守门 PASS_LIMITED；run 40620485456 7/7 jobs通过
- 输入基线：same-run Windows parent candidate ZIP、manifest和payload-sha256sums；父包release_eligible=false、legal_clearance=false，启动前置缺正式产品公钥
- 涉及模块：Windows offline candidate staging与回滚保护；不改业务API、数据库或License实现
- 实体/API/权限：不改业务实体/API/权限；只操作run-owned文件和原子元数据
- 编码前证据：smoke现有清洁提取逐项校验，但包内依赖、服务信任及安装/升级不齐；Release规则要求明确离线升级备份/维护/Migration/health流程。任何runner-only staging不得标成安装或Pilot。
- 本WBS目标：新增受控staging工具，在hosted Windows D盘RUNNER_TEMP隔离根内校验parent archive identity、manifest、无release/legal放行状态及每项payload SHA-256，安全提取至唯一versioned staging目录并生成非敏感staging receipt；任一验证或写入失败时删除本次新建临时目录，不改变旧候选或用户安装根。
- 验收：同run候选成功进入新的run-owned staging目录；ZIP路径穿越、大小写冲突、符号链接、丢失/错配摘要、正式release标志意外改变、目标已存在、目标不在runner D盘等负例拒绝；二次运行不覆盖旧目录；失败清理只触碰验证过的run-owned temp path；不会启动服务/数据库/改变注册表或创建安装快捷方式。
- 偏差：现阶段生产信任未就绪，故A26只验证可回滚的candidate staging，不称产品安装、升级或用户可用；后续要建立正式安装/升级验收前需满足可信源。
- 迁移：无DB migration；无固定安装目录变更。旧候选保持原样。
- 回滚：删除本次Run UUID唯一的runner temp staging目录；测试失败则清理本次路径，绝不递归清理计算出的非runner路径。
- Secret：不读CManager secret内容、不输出日志；仅copy已校验候选内容，不生成密钥/证书或用户凭据。
- 运行边界：只GitHub hosted Windows 2025；解压、生成、校验、清理都限定runner D盘RUNNER_TEMP；用户本机不执行程序。
- 下一步：实施工具及hosted negative/positive staging验证；如CI失败先保留记录修复再重跑。

## 实施前验证计划

1. 固定输入archive digest和manifest identity，再解析ZIP。
2. 执行safe path、casefold唯一、拒绝symlink检查，再校验payload与总数。
3. 验证目标目录规范为RUNNER_TEMP子树且drive不为C，目标新建而不覆盖。
4. 只在staging临时路径解压，逐项hash校验，全部成功才用同volume rename作为完成标志。
5. 在归档及文件系统失败注入时，只清理已验证run-owned staging临时目录；保留其他目录。
