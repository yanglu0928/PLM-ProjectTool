# P06-P12-B01：停止请求与下一次准入边界

2026-09-27，Phase2，输入CR-AUD-004/P06-P10～P12-A。编码前检查：前置外部Console证实活动长阻塞后可能第二次领取；涉及Audit Application Loop/进程signal入口，不涉及实体/API/权限/Schema/依赖变化。验收：主线程已收到停止标志后，不依赖50ms桥线程调度即可在下一Step前request_stop；原pending排空不变；Probe异常失败关闭、不猜完成；handler仍仅置标志。

兼容差异/选择：仅桥线程观察标志会与主线程下一Step竞态。选择显式只读stop_requested callable由signal context提供，Loop每次Step前核精确bool并在正常执行栈request_stop；保桥线程唤醒idle。拒绝在信号handler取锁/DB或强杀。与冻结架构无冲突，作为CR-AUD-004实现修正记录；无数据升级，回滚撤内部扩展保历史。不解决无限阻塞/尚未处理的Python信号，也不等于SCM/真实PG子进程已通过。

验证计划：确定性禁桥线程unit、Probe非法值/异常无claim、原1111回归、P12-A单次长Event.wait活动外部CTRL_BREAK再次验证；真实DB子进程后续独立验证。

结果 INTERNAL PASS：确定性不运行桥线程时，已收到SIGINT标志仍1执行/1领取后STOPPED；非法/异常Probe无claim、错误脱敏。1113项后端通过（2既有权限跳过）。P12-A恢复单次Event.wait(10)，外部CTRL_BREAK释放后排空/不再领取，原handler恢复；没有把无限阻塞标为可停止。开发wheel 631428 bytes，SHA256 `57936f06da7377c4a0ea8dea3d89bc8ee64f1e626bde42cc6ab3ef8c813c20a5`。正式License来源/真实PG子进程/SCM/其他平台/完整安装包与Gate仍待。
