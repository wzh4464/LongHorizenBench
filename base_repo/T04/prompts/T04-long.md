# T04: Apache Airflow — AIP-39 Richer `schedule_interval` / Timetables

## Requirement — self-contained specification

*Upstream reference (do not fetch at runtime):* AIP-39 "Richer `schedule_interval`" at `https://cwiki.apache.org/confluence/display/AIRFLOW/AIP-39+Richer+scheduler_interval`. All the detail required to implement this feature is reproduced below.

---

## 1. Motivation

Airflow's historical `schedule_interval` argument accepts one of:

* A cron expression (`"0 4 * * *"`),
* A `datetime.timedelta` (`timedelta(hours=6)`),
* A preset string (`"@daily"`, `"@hourly"`, ...).

This is insufficient for realistic production schedules because:

1. **No notion of a data interval distinct from the logical run date.** `execution_date` is used as both "the time the job is responsible for" and "the time it was triggered", which leads to confusion.
2. **No support for irregular cadences.** Skip weekends, dispatch Monday only if Friday's run succeeded, "third Friday of the month", fiscal calendars, etc., cannot be expressed.
3. **Extending the scheduler** requires patching Airflow core.

AIP-39 replaces the implicit schedule semantics with an explicit **Timetable** abstraction that lives alongside `schedule_interval`. Existing DAGs keep working; new DAGs can pass a `Timetable` implementation to specify arbitrary cadence logic.

## 2. Concepts

Three named types are introduced:

* **`DataInterval(start: DateTime, end: DateTime)`** — a half-open time window covered by one DAG run. Each run has exactly one `DataInterval`.
* **`TimeRestriction(earliest, latest, catchup)`** — scheduler-supplied bounds that restrict the timetable's scheduling decisions.
* **`DagRunInfo(logical_date, data_interval, run_after)`** — the scheduler contract: when the next run should fire, which data interval it covers, and its nominal logical date.

## 3. `Timetable` abstract class (new module in the Airflow timetables package)

```python
class Timetable(LoggingMixin, ABC):
    description: str = ""
    periodic: bool = True
    can_run: bool = True

    @abstractmethod
    def infer_manual_data_interval(self, *, run_after: DateTime) -> DataInterval: ...

    @abstractmethod
    def next_dagrun_info(
        self,
        *,
        last_automated_data_interval: DataInterval | None,
        restriction: TimeRestriction,
    ) -> DagRunInfo | None: ...

    def serialize(self) -> dict[str, Any]: return {}

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> Timetable:
        return cls()
```

The scheduler calls `next_dagrun_info` each time it evaluates whether a DAG should produce a new DagRun. Returning `None` means "no next run".

## 5. Built-in Timetable subclasses

Airflow ships four built-in timetable implementations:

### 5.1 `NullTimetable`

Used when `schedule_interval=None`. `next_dagrun_info` always returns `None`; the DAG is triggered only manually.

### 5.2 `OnceTimetable`

Used when `schedule_interval="@once"`. Generates a single DagRun starting at the DAG's `start_date`, and never schedules again.

### 5.3 `CronDataIntervalTimetable(cron, timezone)`

Used when `schedule_interval` is a cron string like `"30 * * * *"`. `next_dagrun_info` calculates the next cron tick that is strictly greater than the most recent `last_automated_data_interval.end`; the data interval is `[previous_tick, next_tick)`.

### 5.4 `DeltaDataIntervalTimetable(timedelta)`

Used when `schedule_interval` is a `timedelta`. Similar to above but increments by the fixed delta.

## 6. Integration

- `airflow.models.dag.DAG.__init__` now accepts `timetable=…` OR `schedule_interval=…` (the latter is mapped onto the appropriate `Timetable` subclass).
- The scheduler uses `Timetable.next_dagrun_info(...)` exclusively; the old `schedule_interval` logic is implemented as a compatibility shim around `CronTimetable`.
- New DB columns `data_interval_start` and `data_interval_end` on `dag_run`.

## 7. Plugin protocol

Custom timetables are loaded via the `airflow.plugins_manager` protocol: plugins can register `Timetable` subclasses, which become available via `provide_timetable` or by string reference in serialized DAG JSON.

## 8. Implementation Task

1. Introduce the `Timetable`, `DataInterval`, `DagRunInfo`, and `TimeRestriction` abstractions in a new timetables package.
2. Add the cron-based timetable module containing `CronDataIntervalTimetable` and `DeltaDataIntervalTimetable`.
3. Add a simple timetable module with `NullTimetable`, `OnceTimetable`.
4. Update the DAG model so `schedule_interval` resolves to a `Timetable`; add a `timetable` keyword argument with priority over `schedule_interval`.
5. Modify the scheduler job to query the active timetable for next DagRunInfo.
6. Add Alembic migration introducing `data_interval_start/data_interval_end` columns, backfill from `execution_date`.
7. Wire plugin support so `from __future__ import annotations`-style timetable classes can be discovered.
8. Add unit tests covering the new timetable abstractions.

## 9. Backwards compatibility

- `DAG(schedule_interval='@daily')` continues to work (mapped to `cron="0 0 * * *"` and wrapped in `CronDataIntervalTimetable`).
- `execution_date` remains as a field on `DagRun` but semantics are clarified: it equals `data_interval_start`.
- Existing custom operators continue to see `execution_date` in context.

## 7. Tests and acceptance

- New unit tests cover each built-in `Timetable`, boundary cases (DST, leap days), and edge cases (empty `next_dagrun_info` output).
- The existing scheduler-job test suite continues to pass.
- `dag.iter_dagrun_infos_between(start, end)` returns matching `DagRunInfo` values for legacy cron schedules, identical to pre-change behaviour.
