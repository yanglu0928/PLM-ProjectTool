# CR-EXEC-048：Windows 插件进程树启动期 containment 加固

- 日期：2026-11-07
- 状态：编码前检查通过；实施与 Hosted 验收待完成。
- Phase：Phase 2 Platform Core。
- WBS：PLG-03-A02。
- 上游：PLG-03-A01 Process Host，代码提交 `60a9e2e12e212e4a279fdd765ed6b0032af7d4af`。
- 基线：ADR-005 独立子进程插件协议；CR-EXEC-046 仅传输层范围。
- 类型：安全可靠性加固，不改变已冻结架构或外部接口。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-03-A02 Windows 子进程启动 containment
输入基线：ADR-005；PLG-03-A01 Process Host；CR-EXEC-046；Plugin development/testing rules
前置任务：PLG-03-A01 Hosted Windows Server 2025 合成测试通过（run 42315760138 后端 4,094 tests；Host 7 tests）
涉及模块：apps/backend/src/plm_assistant/modules/plugin/application/process_host.py；其 unit tests
涉及实体：无
涉及API：无
涉及权限：不改变 Plugin capability / signer / Output 授权；进程启动失败保持 fail-closed
验收标准：Windows Hosted 上业务入口执行前即完成 Job Object 归属；无法建立归属时子进程不恢复执行并被终止；合成 child 启动 descendant 后触发超时，验证整个进程树被终止且 descendant 不能在其拥有的 D 盘临时目录落 marker；现有 Host tests、后端全量/wheel继续通过
风险：Windows 主线程定位/恢复 API 存在结构布局与句柄生命周期错误风险
```

## 差异与证据

当前 Host 使用 `subprocess.Popen` 启动子进程，然后创建并分配 Windows Job Object。源码顺序意味着 Python 入口可能在 Job Object 归属完成前开始运行。这是基于实现顺序发现的竞态风险；当前测试没有证明其已被利用或实际逃逸，不按已发生安全事件处理。现有创建新进程组、Job Object kill-on-close 与超时清理保持不变。

## 方案评估与选择

1. 维持启动后分配：代码改动最少，但保留入口抢跑窗口，不采用。
2. Windows 以 suspended 状态创建；在入口运行前将进程分配到 kill-on-close Job Object，随后只恢复其主线程。任一创建/分配/线程恢复步骤失败时保持 fail-closed 并终止子进程。POSIX 路径不变。**选择方案 2。**
3. 重写通用 CreateProcessW/STARTUPINFOEX 调用：控制粒度更强，但会重做 Popen 管道/句柄继承及启动逻辑，超出本次最小任务，不采用。

## 边界、风险处理与回滚

- 仅 synthetic Python child，在 GitHub Hosted Windows Server 2025 的 D-drive runner temp 中执行；禁止本机/C盘运行。
- 不执行真实、客户或第三方插件，不接生产 Output/Worker，不改变 API、DB、Migration、信任根或 package manifest。
- Host containment 或测试失败时停止继续接线，保留证据；通过单独 revert commit 恢复提交 `60a9e2e` 的传输实现，不 force push、不改写冻结基线。
- 通过 Hosted 定向和全量测试后，复查完整流程和无 Secret 变更，再更新本 CR、结果、STATUS、CHANGELOG 并推送。


## 首轮 Hosted 复验

- run [42318583193](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42318583193) 的前端、PG18 sidecar、A17 runner-temp harness、P39/P24/A50成功；Backend 4,095 项套件中新增 Host 7 项出现 5 failures、2 errors。
- 失败均来自新的 Windows suspended-start/Job Object 接线返回固定 `PLUGIN_PROCESS_START_FAILED`，未泄露 child 输出，过程 fail-closed。尚未通过用例证明进程树语义，也未达到该 WBS 验收。
- 具体 API 子阶段未知；不依据调用顺序猜测根因。下一步仅增加阶段枚举与 Win32 整数错误码的内部诊断，保留外部错误码与失败关闭行为，不输出原始异常文本。
- 此测试失败不是产品信任绕过或客户影响；运行只在 Hosted runner D 盘，合成数据；未改数据库/API/信任/Output。修复前保持 PLG-03-A02 `INCOMPLETE`。
