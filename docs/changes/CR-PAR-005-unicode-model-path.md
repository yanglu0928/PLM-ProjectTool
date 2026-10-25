# CR-PAR-005：Windows 中文路径下离线 OCR 模型加载失败

状态：OPEN；日期：2026-09-30；Phase 2 / PAR-01 发行兼容性。原 Gate2 Python3.13/PaddleOCR 选型及既有代码不变，本 CR 登记路径兼容偏差；按持续授权可先分析、验证后实施，不把本次观察写成全平台结论。

## 来源与证据

PLT-MAINT-01-A05-P04 真实 Windows 进程复验时，`artifacts/poc-05/windows-server-2025/bundle-20260917-02/staging/models/PP-OCRv5_mobile_{det,rec}` 位于仓库中文绝对路径。四个模型指纹文件齐全，`_model_fingerprint` 成功，但当前隔离 Python3.13/PaddleOCR3.7.0/PaddleX3.7.2/PaddlePaddle3.3.1 下 `PaddleOCR(...)` 初始化被上层规范化为 `OCR_ENGINE_UNAVAILABLE`；同一模型的本机 ASCII 路径 `C:\Users\17231\.paddlex\official_models\...` 初始化及真实扫描 PDF OCR 成功。尚未证明是 Paddle 本体、底层 C++、路径编码、模型副本内容还是 Windows 文件 ACL 中哪一项导致，不能仅凭路径相关性断言根因。

## 方案与边界

后续定位：两处 det/rec 各四个指纹文件 SHA-256 逐文件完全相同；在当前 Python 环境直接调用 PaddleOCR，中文路径到 `paddle_inference.create_predictor` 时抛 `json.exception.parse_error.101`（首字节读得空内容），同字节 ASCII 路径初始化成功。可确认与当前 Windows/Paddle 版本的路径处理相关，尚不能归因于 PaddleOCR、PaddleX 或 PaddlePaddle 的某一层。Paddle 官方仓库亦有 [中文用户目录导致 inference.json 无法打开的讨论](https://github.com/PaddlePaddle/PaddleOCR/discussions/16061)，仅作风险佐证，不替代本机复现。

- A：规定发行模型只安装在 ASCII 绝对路径，启动时检查并给出固定可操作错误。可作为最小安全兼容方案，但需确认模型副本内容及受控安装目录/ACL，不能据此宣称任意中文路径受支持。
- B：定位并修复底层 Unicode 加载，或在受控私有 ASCII 缓存复制并逐文件校验指纹。仅在有可重现根因和安全/空间/升级/回滚证据后实施；缓存不可放进可被普通用户替换的位置。
- 当前：本轮真实维护门禁验证使用已存在的 ASCII 模型缓存，保留中文路径失败为发行已知问题；不擅自改第三方源码或复制模型到新目录。

选择：按 A 先实现 Windows 启动时的明确路径拒绝，并将正式模型安装目录限定为受控 ASCII 绝对路径；先关闭“看似有效配置但底层空 JSON”这一失败模式。发行安装器、目录 ACL、模型内容校验与 Server2025 实机随后验收，未完成前 CR 仍 OPEN。B 暂不采用，避免未验证的运行时复制/联接和第三方源码改动。

## 影响、迁移、回滚和验收计划

影响 Windows11/Server2025 中文安装路径下的 Parser 启动和扫描 OCR；不涉及 Schema、API、客户内容外发或模型指纹合同。正式解决前安装说明须限定经验证的模型目录，启动失败保持不领取 Job。后续 WBS 在相同模型字节的 ASCII/中文路径、当前账户与目标部署账户、中文系统区域、Windows11/Server2025 上复现；记录底层异常、ACL/文件 Hash、真实离线 OCR 与进程退出/资源清理，回归 Python 单元/PG18/打包。若修复失败，维持 ASCII 模型目录明确限制，不标记三平台发行兼容 PASS。回滚到先前程序与经过校验的模型目录，保留历史证据。

2026-09-30/PAR-01-A05-P06-P01：选择 A 的启动前校验已实现；Windows 非 ASCII 模型绝对路径固定 `OCR_MODEL_PATH_UNSUPPORTED`，不进入 Paddle；单元5、后端全量1674（3既有跳过）、ASCII 目录真实合成 PNG/混合 PDF OCR、wheel PASS。正式受控 ASCII 安装目录/ACL、目标账户/Server2025 与离线包仍未验证；CR 保持 OPEN，不宣称中文目录可运行。
