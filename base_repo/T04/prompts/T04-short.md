**Summary**: AIP-39 重构 Airflow 的调度系统，引入 Timetable 抽象层来替代简单的 cron/timedelta 调度。新设计将 "何时运行" 与 "处理哪些数据" 分离，通过 data_interval（数据区间）概念明确 DAG run 应处理的数据范围。同时重命名 execution_date 为 logical_date，消除长期存在的命名混淆。

**Proposal**: 引入 Timetable 抽象类作为调度逻辑的核心接口，提供计算下一次 DAG run 时间和数据区间的方法。实现多个内置 Timetable（CronDataIntervalTimetable、DeltaDataIntervalTimetable、NullTimetable、OnceTimetable），重构 DAG 类使用 Timetable 替代直接的 schedule_interval 计算，保持向后兼容。
