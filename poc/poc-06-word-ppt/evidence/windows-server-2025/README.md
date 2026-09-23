# POC-06 Windows Server 2025 证据

- 环境：Windows Server 2025 Datacenter 10.0.26100，x86-64，VMware 实机虚拟机。
- 两个纯合成样件通过 VMware Tools 传入，执行只读 OOXML 与 SHA-256 复验。
- DOCX：Hash 与 Windows 11 一致，99 个显式分页、9 个表格、4 个内联图形，包结构 PASS。
- PPTX：Hash 与 Windows 11 一致，50 张幻灯片，包结构 PASS。
- 阻塞：虚拟机未安装 Microsoft Word 与 PowerPoint，不得声称 Office 实开或 PDF 导出已通过。
- 完成后已删除来宾机临时目录并将虚拟机恢复为关机状态。
