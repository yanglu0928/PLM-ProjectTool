# P06-P12：Windows 外部 Console 停止验证

2026-09-27，Phase 2；输入 CR-AUD-004、P06-P10 信号适配器、P06-P11 Windows CLI。前置内部测试通过；本子项 P12-A 仅验证外部控制投递，不替代真实数据库子进程 P12-B。

编码前：模块为验证脚本/原信号入口；实体为合成 Loop/Step；无 API、Migration、依赖或权限变化。验收：独立隐藏 Console，仅本轮目标和发送器在内才允许 CTRL_BREAK；空闲60秒及时停止，活动任务排空且只领取一次，恢复原 handler。风险：错误 Console 广播影响其他程序；不得向父 Console 广播或强杀生产进程。

偏差/选择：原 P10 signal.raise_signal 是进程内信号，不能证明外部 Console 投递。增加独立隐藏 Console 和发送器，先核 Console 进程清单再广播。来源：https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent 、https://learn.microsoft.com/en-us/windows/console/attachconsole 、https://learn.microsoft.com/en-us/windows/console/setconsolectrlhandler 。不改变生产机制。回滚仅撤本验证脚本；冻结历史保留。验证结果待运行；SCM、真实PG子进程、正式信任材料/完整包/Gate未通过。

结果 P12-A INTERNAL PASS：两个真实独立隐藏Windows Console，经另一进程外部CTRL_BREAK，清单严格仅目标+发送器；空闲60秒及时STOPPED/0执行，活动合成执行器50ms可响应等待排空/1执行/1领取、SIGBREAK handler恢复。后端1111测试通过，2既有权限跳过。无生产代码/包/API/Schema改变，不重新声称wheel验证。

失败证据保留：活动合成执行器最初单次Event.wait(10)阻塞主线程，收到信号后释放仍再次输出ACTIVE，不能报单次排空通过。验证脚本改50ms分段等待后通过；这只证明可响应执行器路径，**真实DB/文件阻塞调用及停止标志桥接竞态仍待P12-B核查**，不把测试调整当生产修复。未强杀，故障合成子进程通过私有STOP控制收口。

后续P12-B01：生产Loop新增显式只读停止Probe，在下一Step前正常栈request_stop。脚本已恢复原单次Event.wait(10)，外部CTRL_BREAK再次验证通过，关闭“已处理标志但桥线程未调度导致再领取”这一竞态。等待未返回前仍不保证立即处理信号；真实PG子进程/SCM仍待。详见aud-p06-p12-stop-boundary.md；首次失败记录保留。
