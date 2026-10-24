# POC-09 Windows 11 证据

- Windows 11 x86-64，Python 3.13.15，cryptography 50.0.1。
- 实机枚举 6 个 MAC 候选，只保存候选数量；License Request 不包含原始 MAC。
- 26/26 单元测试、10/10 验收场景 PASS。
- License / MAC / SystemTimeGuard 覆盖率分别为 91% / 92% / 94%。
- 8/8 非法授权场景拒绝；私钥与原始 MAC 落盘数均为 0。
