# 测量与采集参考

## 先选择计时窗口

| 目标 | 可用方法与需要说明的边界 |
|---|---|
| 单kernel设备时间 | 当前安装支持的NPU event或profiler目标task时间；核同设备/stream及事件单位 |
| 多kernel wrapper设备时间 | 在完整设备工作前后放事件，包含所选helper；不能只挑最快目标kernel |
| host端到端 | 单调时钟，窗口边界同步异步工作；说明是否包含拷贝、分配、编译和初始化 |
| 冷启动或编译 | 独立新进程/cache条件，记录初始化与编译；不混入稳态设备耗时 |
| 仿真 | 模型定义的cycle/时间和具体窗口，另记采集墙钟；不与硬件事件样本合并 |

选用项目已有可信计时函数时检查其实现和返回单位。Torch/NPU API、profiler支持及CSV字段随版本变化，先读当前安装或源码；不盲目复制CUDA API或把异步host调用时长当设备耗时。

## 最小执行协议示例

这是可调整的骨架，不是固定样本数：

```text
保存input / variant / binary / metadata / runtime / device映射
建立输入与运行状态，固定同进程的显式指针
完成必要编译、prime和warmup，保留其调用数
按预先声明顺序运行baseline/candidate
  → 每次对应明确call ID、stream及结果
  → 按当前API定义取设备时间或同步后的host时间
检查结果与边界，保存全部样本及异常
必要时反转顺序或另轮复核，检查漂移
```

有状态算子每次恢复一致输入状态；别名、mutation、workspace、随机/稀疏输入及隐藏分配可能改变比较。不同进程无法保证相同指针，按实验目标决定是否需要同进程对照并说明限制。

不要在计时窗口内做未声明的输出读取和精度计算。反过来，测试前的精度通过也不保证之后不同配置、输入或binary正确；按实际被测身份绑定结果。

单样本或小差异不能直接称为稳定收益。样本量和稳定性阈值按差距及成本确定并事先记录；没有频率、健康或独占证据就标明，不为测试改共享卡状态。

## profiler 和 PMU

当前入口可能是安装的 `msprof`、`msopprof`、Torch NPU profiler或项目包装脚本。用实际版本支持的命令/配置，先确认是硬件采集还是simulator。导出布局、平台格式、task筛选字段及指标公式都需要版本绑定。

PMU证据逐层检查：

1. 当前SoC/exporter声明支持所需指标；API enum存在不是能力确认。
2. 请求与采集元数据一致，实际物理卡、PID、stream/task及数量/顺序匹配预声明调用。
3. 导出列完整，NA/缺列/全零单列原因；缺值不是无冲突。
4. 原始任务周期、时间戳及关键字段与CSV相符；跨版本原始格式不能猜偏移。
5. 重复同配置的计数/分布符合可解释范围；必要时复算当前公式。
6. 跨指标的联合特征出现异常时暂停因果归因。即使计时稳定或metadata正确，也可能缺少event-select实际读回证据。

“单指标新进程、一次持续profiler、避免反复start/stop”适合排查跨指标污染，但不是硬件通用保证。进程隔离不保证卡级采集独占；其他profiler、运行时、驱动和导出链路是不同解释，没有证据不要指认其他用户。

## 离线 CSV 汇总

标准化示例：

```csv
variant,round,phase,task_id,duration_us
baseline,1,warmup,a0,20.0
candidate,1,warmup,b0,20.0
baseline,1,timed,a1,10.0
candidate,1,timed,b1,9.0
baseline,1,timed,a2,10.2
candidate,1,timed,b2,9.1
```

使用显式phase选择时保留被排除行数和原因：

```bash
python scripts/summarize_timings.py samples.csv --value-column duration_us \
  --unit us --kind hardware --window kernel-event --round-column round \
  --phase-column phase --phase timed --reference baseline
```

helper报告每轮/版本样本数、均值、中位数、范围、p10/p90及观察到的比率；不自动混合轮次、不修剪长尾、不判断采集独占或显著性。相同样本数也不意味着测量条件相同。

`speedup = baseline / candidate`；`耗时下降% = (baseline-candidate)/baseline*100`。不同shape可报告逐项、几何平均speedup或按目标workload加权总时间；不能不说明权重就把平均speedup当总耗时下降。
