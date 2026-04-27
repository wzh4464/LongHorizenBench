# T03: Apache Kafka — KIP-460 `ElectLeadersRequest` / Unified Leader-Election API

## Requirement (self-contained; no network required)

*Upstream reference (for your records, not fetched):* KIP-460, "Admin Leader Election RPC" (`https://cwiki.apache.org/confluence/display/KAFKA/KIP-460%3A+Admin+Leader+Election+RPC`). The complete specification is inlined below.

---

## 1. Motivation

Before KIP-460, Apache Kafka offered only a *preferred* leader election via the `kafka-preferred-replica-election.sh` script and the corresponding `ElectPreferredLeadersRequest` (API key 37). There was no first-class admin-level operation to force an **unclean** leader election on a partition — operators who needed to restore availability of a partition whose preferred replica was offline had to temporarily flip `unclean.leader.election.enable` at the broker or topic level, then revert it. This is error-prone (the change can be left on accidentally) and unwieldy (requires config churn).

KIP-460 unifies both kinds of leader election under a single admin RPC — `ElectLeaders` — and a single CLI — `kafka-leader-election.sh`. The prior `ElectPreferredLeaders` API and CLI are deprecated but kept for backwards compatibility.

## 2. Public API surface (Java admin client)

### 2.1 `ElectionType` enum

```java
public enum ElectionType {
    PREFERRED((byte) 0),
    UNCLEAN((byte) 1);

    public final byte value;
    ElectionType(byte value) { this.value = value; }
    public static ElectionType valueOf(byte value) { ... }
}
```

### 2.2 `Admin#electLeaders`

```java
default ElectLeadersResult electLeaders(
        ElectionType electionType,
        Set<TopicPartition> partitions) {
    return electLeaders(electionType, partitions, new ElectLeadersOptions());
}

ElectLeadersResult electLeaders(
        ElectionType electionType,
        Set<TopicPartition> partitions,
        ElectLeadersOptions options);
```

- `partitions == null` means "all partitions known to the cluster".
- `ElectLeadersResult` exposes `KafkaFuture<Map<TopicPartition, Optional<Throwable>>> partitions()` and a convenience `KafkaFuture<Void> all()`.
- The existing `Admin.electPreferredLeaders(...)` API stays for source-compatibility; its implementation delegates to `electLeaders(ElectionType.PREFERRED, …)`.

## 3. Wire protocol

### 3.1 `ElectLeadersRequest` (new API key 43)

```
ElectLeadersRequest => api_version election_type topic_partitions timeout_ms
  election_type      : int8        // 0 PREFERRED, 1 UNCLEAN
  topic_partitions   : nullable array of
    name             : string
    partition_index  : array of int32
  timeout_ms         : int32
```

When `topic_partitions` is null, all partitions are targeted.

### 3.2 `ElectLeadersResponse`

```
ElectLeadersResponse => throttle_time_ms error_code replica_election_results
  throttle_time_ms          : int32
  error_code                : int16             // top-level cluster error
  replica_election_results  : array of
    topic                   : string
    partition_result        : array of
      partition_index       : int32
      error_code            : int16
      error_message         : nullable string
```

New error codes:

- `ELECTION_NOT_NEEDED (84)` — preferred election but already leading.
- `PREFERRED_LEADER_NOT_AVAILABLE (80)` — preferred replica is not alive / out of ISR.
- `ELIGIBLE_LEADERS_NOT_AVAILABLE (81)` — applies to UNCLEAN when no replica can be promoted.

## 4. Controller behaviour

- **PREFERRED** election: check each partition; if preferred replica is currently out of ISR or is already leader, raise the appropriate error for that partition, leave others unaffected.
- **UNCLEAN** election: pick any replica as the new leader if none of the in-sync replicas is available; data loss is the caller's concern. The topic's `unclean.leader.election.enable` setting is **not** consulted in this path.
- The controller handles both in the same flow; the only difference is the eligibility rule for new leaders.

Authorisation requires `CLUSTER_ACTION` (previously `ALTER`) on the cluster.

## 5. Client-side deliverables

* `ElectionType` enum (java.lang.Enum).
* `AdminClient.electLeaders(ElectionType, Collection<TopicPartition>, ElectLeadersOptions)`.
* `ElectLeadersResult` with `Map<TopicPartition, ElectionResult>` future.
* `ElectLeadersOptions` with a `timeoutMs(int)` configuration.
* Deprecate `AdminClient.electPreferredLeaders(...)` as a thin wrapper over the new call with `ElectionType.PREFERRED`.

## 6. Command-line tool

Replace `kafka-preferred-replica-election.sh` with a new `kafka-leader-election.sh` supporting the following options:

```
--election-type [PREFERRED|UNCLEAN]
--bootstrap-server host:port
--all-topic-partitions
--topic t --partition p
--path-to-json-file file.json
```

JSON file format:

```json
{
  "partitions": [
    { "topic": "foo", "partition": 0 },
    { "topic": "bar", "partition": 3 }
  ]
}
```

## 7. Implementation Task

1. Add JSON schemas under the Kafka common-message resources directory for `ElectLeadersRequest.json` and `ElectLeadersResponse.json`, versions 0-1.
2. Generate Java classes via the Kafka message generator; wire them into `org.apache.kafka.common.requests`.
3. Add `ElectionType` enum, `AdminClient.electLeaders`, `ElectLeadersResult`, `ElectLeadersOptions` to the public API.
4. Server side: add a handler in `KafkaApis` that routes to `KafkaController.electLeaders`. The controller performs both preferred and unclean elections via the existing `PartitionStateMachine`.
5. Implement the `kafka-leader-election.sh` CLI by adding a new admin command class for leader election.
6. Add tests: `ElectLeadersRequestTest`, `ElectLeadersResponseTest`, `AdminClientIntegrationTest#testElectLeaders`, and a CLI smoke test.
7. Deprecate (but do not remove) `electPreferredLeaders` in `AdminClient` and the `kafka-preferred-replica-election.sh` script.

## 8. Acceptance

- `kafka-leader-election.sh --election-type unclean --all-topic-partitions --bootstrap-server ...` completes without permanently changing any topic config.
- The new API key (43) is advertised by brokers and understood by the client.
- All integration tests pass; existing `electPreferredLeaders` clients continue to work against a broker that now implements `electLeaders`.
