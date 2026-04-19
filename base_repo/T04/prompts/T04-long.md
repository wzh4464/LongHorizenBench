# T04: Apache Airflow

## Requirement
https://cwiki.apache.org/confluence/display/AIRFLOW/AIP-39+Richer+scheduler_interval

---

**Summary**: AIP-39 重构 Airflow 的调度系统，引入 Timetable 抽象层来替代简单的 cron/timedelta 调度。新设计将 "何时运行" 与 "处理哪些数据" 分离，通过 data_interval（数据区间）概念明确 DAG run 应处理的数据范围。同时重命名 execution_date 为 logical_date，消除长期存在的命名混淆。

**Motivation**: 当前 Airflow 调度存在两个核心问题：1) 调度灵活性不足——只能用 cron 或 timedelta，无法表达复杂场景如 "仅工作日运行"、"发薪日运行"、"交易日运行" 等；2) execution_date 命名极其误导——它实际表示数据区间的开始时间而非任务执行时间，导致新用户困惑和代码错误。AIP-39 通过引入可插拔的 Timetable 抽象和清晰的概念命名解决这些问题。

**Proposal**: 引入 Timetable 抽象类作为调度逻辑的核心接口，提供 `next_dagrun_info()` 方法计算下一次 DAG run 的时间和数据区间。实现多个内置 Timetable：CronDataIntervalTimetable（cron 调度带数据区间）、DeltaDataIntervalTimetable（timedelta 调度）、NullTimetable（手动触发）、OnceTimetable（一次性运行）。重构 DAG 类使用 Timetable 替代直接的 schedule_interval 计算，保持向后兼容。

**Design Details**:

1. Timetable 基类（airflow/timetables/base.py）：定义 Timetable 抽象接口，核心方法：
   - `next_dagrun_info(last_automated_dagrun_date, restriction) -> Optional[DagRunInfo]`：计算下一个 DAG run 的信息
   - `infer_data_interval(run_after) -> DataInterval`：推断指定时间点的数据区间
   - DagRunInfo 包含 run_after（最早调度时间）和 data_interval（数据范围）

2. 数据区间类型（airflow/timetables/base.py）：定义 DataInterval（包含 start 和 end）和 TimeRestriction（调度约束，包含 earliest、latest、catchup 标志）。

3. 内置 Timetable 实现：
   - CronDataIntervalTimetable（airflow/timetables/interval.py）：基于 cron 表达式，数据区间为两次触发之间
   - DeltaDataIntervalTimetable：基于 timedelta，数据区间为固定时长
   - NullTimetable（airflow/timetables/simple.py）：schedule_interval=None 的场景
   - OnceTimetable：schedule_interval='@once' 的场景

4. Schedule 封装（airflow/timetables/schedules.py）：封装 cron 解析和下一触发时间计算逻辑，处理 DST 时区转换问题。

5. DAG 类重构（airflow/models/dag.py）：
   - 添加 timetable 属性，从 schedule_interval 自动推断或直接指定
   - 重构 following_schedule/previous_schedule 方法委托给 timetable
   - 添加 get_run_dates 方法替代废弃的 date_range
   - 废弃 is_fixed_time_schedule 方法

6. DagRun 扩展（airflow/models/dagrun.py）：添加 data_interval_start 和 data_interval_end 属性，存储实际的数据区间。

7. TaskInstance 更新（airflow/models/taskinstance.py）：调整与 data_interval 相关的逻辑，确保任务实例能访问正确的数据区间信息。

8. BackfillJob 修改（airflow/jobs/backfill_job.py）：更新 backfill 逻辑使用 get_run_dates 并正确设置 align 参数。

9. 依赖检查更新（airflow/ti_deps/deps/prev_dagrun_dep.py）：更新前置 DAG run 依赖检查逻辑适配新的调度模型。

10. CLI 更新（airflow/cli/commands/dag_command.py）：更新 dag next-execution 命令输出格式。

11. 异常类型（airflow/exceptions.py）：添加 AirflowTimetableInvalid 异常用于 timetable 配置错误。

12. 类型兼容（airflow/compat/functools.pyi）：添加 cached_property 类型存根解决 mypy 类型检查问题。

13. 序列化支持（tests/serialization/test_dag_serialization.py）：确保 DAG 序列化/反序列化正确处理 timetable。

14. 测试：
    - tests/timetables/ 目录下添加各 Timetable 实现的单元测试
    - 更新 tests/models/test_dag.py 测试新的调度逻辑
    - 更新 tests/jobs/test_backfill_job.py 和 test_scheduler_job.py
