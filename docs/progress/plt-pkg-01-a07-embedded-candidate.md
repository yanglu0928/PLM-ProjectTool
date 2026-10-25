# PLT-PKG-01-A07：Windows11 私有运行时与前端新候选

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；本项仅非发行候选，不进入 Gate6。
- 当前 WBS：PLT-PKG-01-A07。
- 输入基线：A02 前端冻结构建，A05 官方 Python3.13.15 embed，A06 93 wheel 私有旁装及清洁 PATH 导入，V2.1 离线交付/第三方许可要求。
- 前置任务：上述本机验证均已通过；正式签发、数据库、OCR 模型、插件和安装升级未齐备，因此仅可组装 `release_eligible=false` 候选。
- 涉及模块：发行准备工具和 Git 忽略的新归档；不修改现有 A03 ZIP、业务实体、Schema、API 或权限。
- 验收标准：仅纳入受控 runtime/前端 dist/非敏感配置；排除运行时生成的 `__pycache__` 和构建机脚本；生成每文件 SHA-256、第三方包元数据清单与缺项标记；ZIP 内清单回读验证、私有解释器导入复验；旧候选保留。
- 风险：A01/A02 来源提交不同，A06 包含尚未完成许可审查的第三方内容；文件清单和归档完整性不等于正式签名、干净客户机安装或业务可用。任何许可元数据不完整均维持 `REVIEW_REQUIRED`；新增归档不上传 Git、不交付客户，可撤工具及经路径核对的新建忽略目录回滚。

## Windows 11 执行结果

```powershell
py -3.13 tools/package_windows_embedded_candidate.py `
  --runtime 'artifacts/package-prep/windows11/embedded-backend-20261001-003655-949d77fb/runtime' `
  --frontend-run 'artifacts/package-prep/windows11/frontend-20260930-232337-333c6e42' `
  --backend-summary 'artifacts/package-prep/windows11/backend-20260930-230837-1ff07b2b/summary.json' `
  --config 'apps/backend/config/bootstrap.example.yaml' `
  --output-parent 'artifacts/package-prep/windows11'
py -3.13 tools/verify_windows11_embedded_candidate.py `
  --archive 'artifacts/package-prep/windows11/embedded-candidate-c81aa7bff37a/NOT-FOR-RELEASE-windows11-embedded-candidate.zip' `
  --output-parent 'artifacts/package-prep/windows11'
```

- 新归档：`artifacts/package-prep/windows11/embedded-candidate-c81aa7bff37a/NOT-FOR-RELEASE-windows11-embedded-candidate.zip`，298,508,820 字节，SHA-256 `a711f492d57fb6e43600d0a52a82283ad21ddab3d875e30ba9395746ad908779`。只纳入原先 A06 的私有 runtime、A02 的 dist 与非 Secret bootstrap；排除 3,222 个运行后产生的 `__pycache__` 文件及构建机 `packages/bin` 脚本；旧 A03 ZIP 保留不改。
- 载荷 17,206 文件、归档共 17,209 条目；每文件 SHA-256 从 ZIP 流回读相符。归档 manifest 固定 `release_eligible=false`、混合来源检查点及缺项；第三方清单有 93 个发行包，全部 `REVIEW_REQUIRED`。其中 40 个声明 `License-Expression`、89 个找到可识别通知文件；`bce-python-sdk` 与本项目后端 wheel 未从当前元数据/通知文件找到许可标记，不等于判定其法律授权状态，需专项补齐。
- 新目录 `artifacts/package-prep/windows11/embedded-reinstall-cd9e8cb947a6/` 从 ZIP 解包后，解释器在清洁 PATH/PYTHONPATH 下导入本包/FastAPI/psycopg/Paddle，`sys.path` 全在私有 runtime，93 个 `.dist-info` 且无 pip；归档的 `NOT-FOR-RELEASE`、第三方许可待审、路径、计数和 Hash 均复核。打包/复验合成单元测试 6/6 PASS（含越界与伪发行声明拒绝）。
- 结论：`WINDOWS11_EMBEDDED_CANDIDATE_REINSTALL_PASS / RELEASE_BLOCKED`。第三方许可/SBOM、正式 License、公钥/客户许可、PostgreSQL18/pgvector、OCR 模型、HTTPS/服务账户、Plugin、安装升级及三平台/Gate/UAT 仍缺；未在物理断网或干净客户机运行完整业务流程。归档不得交付客户，二进制与客户资料均未提交 Git。
