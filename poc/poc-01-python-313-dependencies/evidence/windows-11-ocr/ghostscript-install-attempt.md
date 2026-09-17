# Ghostscript 安装尝试记录

## Result

`INCOMPLETE`

## Failure Analysis

官方 Ghostscript 10.08.0 Windows x64 安装包下载成功，SHA-256 与官方发布记录一致。使用静默参数启动后，安装进程在当前非交互执行环境中持续等待且未产生安装目录，为避免遗留挂起进程已终止。

## Root Cause

当前证据只能确认安装程序需要当前自动化环境无法完成的交互或权限流程；尚不能断言是安装包兼容性问题。

## Impact

- 本轮不能验证 Ghostscript 二进制及 PDF/A 输出路径。
- OCRmyPDF 普通 PDF 输出可在关闭优化时独立验证，不代表 PDF/A 路径已通过。
- Ghostscript AGPL/商业双许可证会影响未来闭源客户发行方式，发行前必须完成许可证评审。

## Option A

在可交互管理员会话中安装官方 Ghostscript，并在三个目标平台分别验证 PDF/A 输出。优点是覆盖完整能力；缺点是需要管理员环境和许可证决策。

## Option B

第一版 OCR 链限定为普通 searchable PDF 输出，不随闭源发行包分发 Ghostscript。优点是降低发行许可风险；缺点是不覆盖 PDF/A 和相关优化能力。

## Recommendation

本轮继续验证普通 PDF OCR 链。将 Ghostscript 安装和 PDF/A 纳入 POC-05，将发行许可证选择纳入 POC-09；未经用户确认，不修改现有 OCR 技术基线。

## Sources

- Ghostscript 官方下载与许可证说明：https://ghostscript.com/releases/gsdnld.html
- Ghostscript 官方发布制品：https://github.com/ArtifexSoftware/ghostpdl-downloads/releases
