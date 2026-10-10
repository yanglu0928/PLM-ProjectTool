# PLT-PKG-01-A08-P03：许可材料并入新非发行候选

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；仅非发行候选。
- 当前 WBS：PLT-PKG-01-A08-P03。
- 输入基线：A07 完整性验证 ZIP、A08-P02 原 wheel 152 份许可材料 sidecar 与来源 Hash。
- 前置任务：A07/A08-P02 本机验证通过；正式许可/Release Gate 未通过，因此不得标记可发行。
- 涉及模块：本地候选打包工具及忽略目录下的新 ZIP；无业务实体、API、权限、Schema、Migration。
- 验收标准：先完整验证源 ZIP 与 sidecar 候选绑定，再生成独立新 ZIP；新增 152 份材料、全部载荷 Hash 回读；全新解包、私有解释器/93发行元数据复验；旧 ZIP 不覆盖。
- 风险：整包内容完整性不是许可证法律审查、签名或客户机安装。撤工具及经路径核对的新忽略目录可回滚，旧 A07 ZIP 保持可追溯。

## Windows 11 验证

- `py -3.13 -m unittest tools.tests.test_augment_windows_candidate_licenses`：2/2 PASS，覆盖 sidecar 完整性及绑定/篡改拒绝。A08-P01/P02/P03 定向合计 9/9 PASS。
- 新 ZIP：`artifacts/package-prep/windows11/embedded-licensed-candidate-af0eba436eae/NOT-FOR-RELEASE-windows11-embedded-candidate.zip`；299,340,162 字节；SHA-256 `45266626dce7d08ed1e46a366cb0b0a901efa78d1fb42dbc781eaabccd92c4d7`。源 ZIP Hash 与 sidecar manifest 绑定；旧载荷 17,206 + 新许可材料 152 = 17,358。新 ZIP 全部 17,358 项 Hash 回读 PASS；manifest 保持 `release_eligible=false`/`REVIEW_REQUIRED` 并记来源 Hash。旧 A07 ZIP 未覆盖。
- 全新解包 `artifacts/package-prep/windows11/embedded-reinstall-2cbdc2c19469/`，解包后 152 份许可材料存在；私有 Python 清洁 PATH/PYTHONPATH 导入本包/FastAPI/Paddle 等 PASS，93 个 `.dist-info`，无 pip；验证器返回 `WINDOWS11_EMBEDDED_CANDIDATE_REINSTALL_PASS`。未实测物理断网、DB/OCR 模型、正式服务或目标机升级。
- 本 ZIP 仍缺 `bce-python-sdk` 0.9.79 对应发行源许可文本和本产品自身许可声明，前端、原生/系统组件、Ghostscript、模型、Plugin 等许可清单及义务复核未完成；`release_eligible=false`，不得交付客户。

## 后续

`PLT-PKG-01-A08-P04` 查明 `bce-python-sdk` 精确版本来源/许可文本并做前端与原生组件证据扩展；随后才可开始法律/发行审核。即使该项通过，正式信任源、DB/OCR/Plugin、安装升级、三平台及 Gate/UAT 仍须独立验收。
