# CR-PAR-004：离线 OCR 依赖版本冲突

状态：Windows11 隔离环境内部 PASS，正式离线发行验收待；日期：2026-09-30；Phase 2 / PAR-01-A05-P01-P05-A02-P03-A03。原冻结 Gate2 选型（Python3.13 / PaddleOCR）不变，调整的是开发包内补丁版本与传递依赖锁定。

## 来源与冲突证据

当前 `apps/backend/pyproject.toml` 固定 `PyYAML==6.0.3`、`paddleocr==3.7.0`、`paddlepaddle==3.3.1`。为 Windows11 隔离 OCR 验证安装后，pip 解析 `paddlex==3.7.2`，其已安装发行元数据要求 `PyYAML==6.0.2`；恢复项目当前 6.0.3 后 `pip check` 明确报版本冲突。实际本机 PP-OCRv5 mobile det/rec 离线模型与合成图片/混合 PDF 在 6.0.3 下虽能运行，但不可把有依赖冲突的环境做发行依据。

官方 PyYAML [发行说明](https://github.com/yaml/pyyaml/releases)记载 6.0.2 支持 Python3.13，6.0.3 主要增加 Python3.14/自由线程实验支持；本项目锁定 Python3.13。该来源只支持选型理由，不代替 `pip check` 与产品回归。

## 方案比较与选择

- A：维持 6.0.3、忽略 `pip check`。拒绝；离线安装依赖不可自洽。
- B：将项目 PyYAML 固定为 6.0.2，并显式固定已验证的 PaddleX 3.7.2。选择；不改 OCR 主次技术选型，减小解析漂移。
- C：寻找另一 PaddleX 版本或维护私有补丁。当前无已验证兼容版本，扩大供应链和测试面，留作 B 失败后的备选。

## 影响、迁移、回滚与验证

只改 Python 包依赖锁定与第三方版本记录；不改 Schema、API、业务权限、模型文件/指纹、客户数据或 License。现有部署在人工备份、维护模式、离线升级时重建依赖环境并跑 `pip check`，不原地覆盖运行中的包。回滚保留原依赖声明的 Git 历史；若 B 失败则停用 Parser 发行入口，不强制把 6.0.3 混入 PaddleX 环境。

验收：隔离 Python3.13 环境 `pip check` 无冲突，真实离线模型合成 PNG/混合 PDF OCR，后端全量回归、wheel 构建和依赖元数据检查。Windows Server2025、Debian13及最终完全离线 wheelhouse 安装另验；这些缺项不随本 CR 自动关闭。

## 执行证据与剩余风险

Windows11 隔离 Python3.13 环境先恢复 6.0.3，实际 `pip check` 报 PaddleX 3.7.2 与 PyYAML 精确版本冲突；调整声明并在隔离环境安装 6.0.2、重装项目元数据后 `pip check` 为 `No broken requirements found`。现有本机 PP-OCRv5 mobile det/rec 显式目录和复合指纹，模型源检查关闭，合成 PNG 一行及混合 PDF 原生/OCR 各一页实跑 PASS；后端全量1657（3既有跳过）、wheel PASS，wheel METADATA 精确包含 `paddlex==3.7.2` 与 `PyYAML==6.0.2`。模型未提交 Git，网络未物理断开，尚未证明全依赖 wheelhouse/三平台断网安装或正式进程。原 6.0.3 声明保留 Git 历史，未碰生产数据。
