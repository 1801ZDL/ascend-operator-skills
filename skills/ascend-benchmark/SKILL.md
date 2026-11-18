---
name: ascend-benchmark
description: 测试和比较 Ascend/Triton 算子的设备性能，设计同条件基线、计时窗口、预热与采样，核对profiler任务和PMU质量。用于真实耗时测量；仿真采集和瓶颈改写分别使用相关专项。
---

# Ascend 算子性能测试

先定义要比较的量：单 kernel、完整 wrapper、多个 kernel 的组合，还是 host 端到端。分别记录编译/预热/首次运行与稳态，不把窗口缩短都写成完整算子加速。

## 建立可比实验

确认输入、有效工作、dtype/stride、语义、参考与候选 binary/metadata及实际入口。使用当前条件下合理的强基线；相对旧实验或较弱机制对照变快不能当作超过当前默认实现。

使用现有设备分配与访问约定，记录物理卡与进程内逻辑编号、运行时、计时方式和可见干扰。设置可见卡需发生在运行时初始化前；不要假定变量名或逻辑 0 的物理映射，按安装版本和采集元数据核对。一次空闲/健康快照不等于独占保证，也不自行锁频、重置卡或终止他人任务。

用能区分候选差异且成本适当的样本规模。先预声明 prime/warmup 与计时样本、版本顺序、轮次、超时及完成条件；短交错 A/B 或 ABBA/反序可减少单向漂移，但不是固定必须次数。记录全部计划内样本、失败和长尾，不按耗时猜版本或事后挑最快窗口。

核对目标 kernel 确实执行，host 异步提交是否已同步、stream 与输出比较是否对应。编译/cache、autotune、profiler schedule或多 kernel wrapper可能放大调用数量；目标调用、所有设备调用和计时样本分别计数。

## 获取计时与 PMU

当前工具/API和指标能力见 [测量参考](references/measurement.md)，按实际版本选择 Torch NPU event、可信 benchmark helper 或 profiler。避免在时间窗口内加入不必要的 tensor 构造、精度比较或调试观测。

指标含义或支持表缺失时，可用 [知识检索](../ascend-knowledge/SKILL.md) 查对应版本资料；仍以当前 exporter、原始计数和 task 映射核对。KG 中其他设备的性能数值不能替代本轮基线。

profiler 对应关系用 PID、物理卡、stream、task、kernel 和时间戳绑定，不以 CSV 行号或耗时分类。API 枚举存在不代表当前 SoC 和 exporter 支持指标。缺列、NA、全零和重复计数异常分别报告，不能都写为零冲突。

同卡无并行采集证据不足时，不将 PMU 作为硬件根因的唯一依据。必要时一个指标一个新进程、进程内一次持续采集，检查重复计数和实际原始字段；这是一种排查方式，不是所有工具的固定规范。

## 汇总结果

保留原始样本和调用映射，报告单位、计时窗口、样本数/轮次、中心值及离散程度。比较 speedup 与耗时下降比例要用正确分母；不同窗口、设备、指标组或运行条件不混成一个平均值。明确未证明的频率/独占/稳定性边界。

离线 CSV 可用 `scripts/summarize_timings.py`：

```bash
python scripts/summarize_timings.py samples.csv --value-column duration_us \
  --unit us --kind hardware --window kernel-event \
  --round-column round --reference baseline
```

脚本只汇总显式列和可选的 phase；未指定 phase 时使用输入的全部行，包括其中的 warmup。需要排除时显式筛选或使用 `--phase-column phase --phase timed`。它不删除异常值，不自动证明可比性、统计显著性或 PMU 合格。负收益同样保存；若没有新性能信号或覆盖价值，不继续无界扩测。
