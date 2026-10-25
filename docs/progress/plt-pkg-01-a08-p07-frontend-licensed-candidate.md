# PLT-PKG-01-A08-P07：前端许可材料并入新非发行候选

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；仅非发行候选。
- 当前 WBS：PLT-PKG-01-A08-P07。
- 输入基线：A08-P03 含 152 份 wheel 许可材料的新候选、A08-P06 六份前端精确 LICENSE sidecar、A02 冻结三文件 dist Hash。
- 前置任务：上述来源完整性通过；法律/Release Gate 未通过，不得发行。
- 涉及模块：本地独立候选组装工具与 Git 忽略的新 ZIP；无实体、API、权限、Schema、Migration。
- 验收标准：sidecar 锁定的 A02 三文件 Hash 与原候选内前端逐项相等；六份许可材料 Hash 验证；生成独立新 ZIP、整包逐文件 Hash 回读；全新解包/私有运行时导入和文件存在检查；旧包保留。
- 风险：许可材料入包不等于已履行全部分发义务或具备客户运行环境；可撤独立工具和经路径核对的新忽略目录回滚，A08-P03 ZIP 保持不变。

## Windows 11 验证

- 新 ZIP：`artifacts/package-prep/windows11/embedded-full-notice-candidate-ad21bbbee647/NOT-FOR-RELEASE-windows11-embedded-candidate.zip`，299,345,824 字节，SHA-256 `6b42945167c4d93330a058f0550a4f8dfd26277287c7a7cf07c536ce400fd77a`。A08-P03 17,358 载荷 + 前端六份 = 17,364；全数逐文件 Hash 回读 PASS。manifest 记录前身候选/sidecar Hash，仍 `release_eligible=false`/`REVIEW_REQUIRED`。
- 全新解包 `artifacts/package-prep/windows11/embedded-reinstall-491d9003aced/`：新增前端许可文件 6/6 存在，候选校验器复验 17,364 载荷/93发行元数据、清洁 PATH 的私有 Python 导入 PASS。并包工具合成 2/2 PASS（前端 dist 与 sidecar 绑定、许可材料篡改拒绝）。
- 旧 A07、A08-P03 候选保留，未覆盖；二进制仍在本地 Git 忽略目录，不推送或交付客户。

## 结论与后续

`WINDOWS11_FRONTEND_NOTICE_CANDIDATE_REINSTALL_PASS / RELEASE_BLOCKED`。仍缺 `bce-python-sdk` 精确发行独立许可文本与本产品许可、原生/系统组件及模型清单/审查、正式 License 信任源、数据库/OCR/Plugin、安装升级、三平台和 Gate/UAT。下一项 `PLT-PKG-01-A08-P08` 核对候选中的原生/系统依赖和 Ghostscript/OCR 发行要求；不得把当前候选作为可使用发行包。
