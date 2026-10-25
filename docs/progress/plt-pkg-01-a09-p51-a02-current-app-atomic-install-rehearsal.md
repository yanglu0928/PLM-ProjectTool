# PLT-PKG-01-A09-P51-A02：当前应用候选原子落地隔离演练

日期：2026-10-25；状态：`IMPLEMENTED_UNIT_PASS_CANDIDATE_RUN_PENDING`；变更依据：`CR-PKG-011`。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；当前 WBS：`PLT-PKG-01-A09-P51-A02`。
- 输入基线：P47 当前应用 `WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE` 清单/哈希结构、P39 私有 staging→逐件复制和读回→同卷原子 rename 失败关闭模式、CR-PKG-011。
- 前置任务：P51-A01 已确认正式启动缺产品公钥而阻塞，并按 A06-P02 转向非发行安装链；CR-PKG-011 已先行记录旧 P39 工具绑定旧候选种类的兼容差异与所选方案。
- 涉及模块：新增 Windows 当前应用候选的开发/验收演练工具及独立测试；不修改旧 P39 实现。
- 涉及实体/API/权限：无业务实体、API、数据库、权限或 License 行为变化；没有实体服务器、无数据库启动、无 SCM/防火墙/证书改动。
- 验收标准：只接受调用方固定的当前应用非发行候选 SHA、其manifest类型/发行禁用标志和全量 payload 清单；源暂存区需来自既有独立清洁提取验证；目标为全新 ASCII Temp 直属根；目标文件集与源逐件一致、哈希全量读回后才原子发布；已有目标、正式 `C:\PLMTool`、路径逃逸、链接、哈希错配必须拒绝；复制故障只能清理本次工具拥有的私有部分目录，ZIP SHA 前后不变。
- 风险：仅证明候选的隔离文件落地与完整性，不代表真正服务启动、正式信任、应用可用、Pilot或发行通过。临时空间不足或强杀可能留下未发布的私有待恢复目录；不自动清理未知项。
- 预计修改文件：`tools/install_windows_current_app_candidate_rehearsal.py`、对应 `tools/tests/` 测试、进度/状态/版本说明与 CR 验收结果。

## 实施与单元验收

- 新增与 P39 独立的当前应用候选演练器：读取当前 candidate kind、不可发行标志及 checksum manifest；与既有清洁 stage 逐件重验；只映射到 `target/app/<payload-relative-path>` 并创建空 `plugins/data/logs/license/runtime` 根目录；复制写后 fsync、逐件读回与全集检查后同卷 rename。
- 明确结果标记 `formal_install_performed=false`、`services_changed=false`、`database_started=false`、`release_eligible=false`。旧 P39 工具及 P33 固定验收未修改。
- 定向测试：5 passed，覆盖映射、非 payload/Windows 大小写冲突拒绝、隔离原子落地/哈希与非发行标志、注入复制中断后目标不存在且私有临时目录清除、已有目标保留并拒绝。第一轮调用系统 Python 因未安装 pytest 无法收集；切换项目既有 Python 3.13 环境后测试通过；没有断言失败。
- 当前仅完成实现与单元检查；从最新干净提交重建候选并执行真实 Windows 临时布局/读回验证待运行，因此 WBS 尚未 PASS。此工具不启动应用、PG 或 Caddy；实际包内运行/UAT另项验证。
