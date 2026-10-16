# PLT-PKG-01-A08-P09-P05-P03-A07-P03-P03：JBIG TIFF 升级预检

日期：2026-10-01；状态：`READ_ONLY_POC_PASS / INSTALLER_INTEGRATION_OPEN`。

编码前检查：Phase 2、Gate 2 已冻结、Gate 3 未通过；CR-PKG-004 已先记录格式能力收缩；输入为 A07-P02 旧/新 `tiffcp` 区分负例与 libtiff4.7.2 `tiff.h` 中 `COMPRESSION_JBIG=34661`。本 WBS 仅做离线只读 TIFF 元数据预检原型，不能将其当作正式安装器或客户数据扫描授权；不改 Parser、数据库、API、License 或当前部署状态。验收为经典 TIFF/BigTIFF、大小端、多页/子目录正反例，实际 JBIG 测试样本识别；解析异常失败关闭，输出不含文档正文或客户路径。风险是 TIFF 变体/损坏文件导致拒绝升级；回滚为撤原型脚本，旧候选与已有数据均不动。正式整库清单、转换/阻断 UI、恢复演练与升级集成仍单独待办。

结果：`tools/scan_tiff_jbig_preflight.py` 按有界随机读取扫描 TIFF/BigTIFF IFD 压缩标签及多页、SubIFD；遇 JBIG 34661 输出 `BLOCK_JBIG`，格式错误/缺文件/循环等输出 `BLOCK_UNKNOWN`，两者均 `upgrade_allowed=false` 且进程非零。只在所有指定文件清晰非JBIG时给 `CLEAR`；输出只含汇总计数、不回显路径或文件正文。大小端/BigTIFF、多页/SubIFD、畸形/循环 3组单元测试PASS；真实本机合成 JBIG 压缩 TIFF 与未压缩 TIFF 同批扫描为 JBIG=1/CLEAR=1、阻断，单独未压缩文件为 CLEAR，缺文件为 BLOCK_UNKNOWN。

边界：这是调用方显式指定的文件列表扫描，不会自动枚举 Document/FileObject 或覆盖所有存量文件。未验证 TIFF 中非标准私有 IFD、加密/嵌套容器，不能保证识别全部客户数据格式；不提供转换功能。正式升级前必须从实际元数据生成完整快照清单、确定扩展名/魔数及保存位置、与新旧运行时做带数据升级/回滚演练，若清单不完整或任何 `BLOCK_*` 必须失败关闭。当前不能据此允许正式升级，`release_eligible=false`。
