# PLT-PKG-01-A09-P51-A18：完整父包候选整合前置检查

- 日期：2026-10-27
- 状态：编码前检查通过，限于同一 GitHub Actions run 内整合可重现的非发行组件候选。
- 输入：更新后 `STATUS.md`；`.ai/SKILL.md`；规则 V1.1；plm-project-development Skill；A17依赖/embedded前置和run 40456511998产物证据。
- 当前分支：`feature/p51-embedded-runtime-cache`，PR #55；禁止直接向 `main` 写入。
- 用户约束：程序不得在用户本机或C盘运行；仅使用GitHub hosted runner，本轮云端构建与临时文件落在runner临时目录。

## 当前可用输入与证明

最新完整同提交Actions run `40456511998` 的源代码后端wheel、frontend dist、Windows PG18/pgvector sidecar、Python embedded base及embedded backend集成job全部成功。嵌入式后端artifact `12712399237` 为296,905,110 bytes，非发行并于2026-11-10到期。PG18 sidecar仍是独立非发行artifact，run `40456511998` 重建成功，55,943,338 bytes；前端dist构建成功。所有artifact必须由该run按明确名称下载，验证source commit/Run身份、manifest/hash和归档路径后才能整合；当前artifact仅在Actions保留期内可用。

现有 `tools/package_windows_embedded_candidate.py` 不可直接作为父包生成器：其输入协议依赖Windows11离线重建stage、历史93 wheels/93 distributions、3-file dist和旧manifest状态，不适用于新hosted来源；不得只去掉数量断言复用。

## 本 WBS 单一问题

把同一GitHub Actions run生成的embedded backend runtime、frontend生产资源和PG18/pgvector runtime组合成一个新的不可变、可校验、明确标注非发行的父包候选，并在上传前验证组件摘要与完整包摘要读回。该项不执行安装、服务启动、OCR模型推理或Edge验收；后续单独WBS做临时隔离安装/运行链。

## 设计/验收约束

- 新增同run assemble job，依赖 backend、frontend、PG18 sidecar和embedded backend job；仅通过Actions artifact传递，不向仓库提交大型构件。
- 必须验证各输入的相同source commit和run身份；读取各自manifest/hash清单并逐文件校验；拒绝重复/大小写冲突/越界ZIP路径、符号链接、缺项、未知敏感扩展名及release/legal=true输入。
- 输出布局清楚区分 `payload/runtime`、`payload/frontend/dist`、`payload/pgsql`、`payload/third-party-licenses` 和各组件原始manifest/inventory；不得将PG安装目录与应用runtime混写。
- 输出总manifest保留各组件identity/hash、总文件inventory、非发行/未法律放行与未覆盖的安装、账户ACL、OCR模型、插件/信任、UAT/Gate等缺口；生成总摘要后再次打开归档逐项读回。
- Build产物只能作为完整性通过的非发行父包候选，不得标作Pilot可用、正式兼容或Release。
- 输入artifact来自过期/非同commit/无法验证时直接失败关闭，不从本机目录或旧93项stage回退。
- 回滚仅丢弃本次失败候选，不变更冻结API/Schema/架构或产品配置。CR-EXEC-005～010继续保留其历史证据。

## 剩余不确定性与下一步

- Actions artifact上传/下载目录及PG sidecar checksum布局在workflow里是明确的；新builder应绑定这些准确路径并核对组件manifest中的身份，不猜测。
- 旧config例子不能直接证明生产服务启动配置正确；本WBS把经过检查的脱敏bootstrap example作为独立配置样例，不含密钥。
- 完成后独立验收：workflow必需依赖关系、组件run/source身份、hash/路径与污染拒绝、总归档清单/逐文件读回、上传门禁。其后进入单独包内临时根部署任务。
