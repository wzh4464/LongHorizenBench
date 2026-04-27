# T01: Apache Kafka — KIP-595: A Raft Protocol for the Metadata Quorum

## Requirement (inlined — no external network access needed)

*Upstream source, for reference only:* KIP-595 on the Apache Kafka Confluence wiki (`https://cwiki.apache.org/confluence/display/KAFKA/KIP-595%3A+A+Raft+Protocol+for+the+Metadata+Quorum`). All information required to implement this task is reproduced below; the agent **must not** attempt to fetch the upstream page.

---

## 1. Motivation

Apache Kafka has historically required an external Apache ZooKeeper ensemble to elect a controller and store cluster metadata (topic configs, partitions, ACLs, ISR updates, etc.). KIP-595 removes that dependency by introducing a **self-managed metadata quorum**: a small set of Kafka brokers agree on metadata via a Raft-style consensus protocol and persist it in an internal `__cluster_metadata` topic. Together with the follow-up KIP-500 this enables single-binary clusters without ZooKeeper.

The protocol is a **Kafka-flavoured Raft** rather than textbook Raft. It reuses Kafka’s existing log layout (epoch-tagged records, leader epoch caches, `Fetch` RPC) and differs from Raft in three places:

1. **Pull-based replication** — followers `Fetch` from the leader instead of the leader pushing `AppendEntries`. This mirrors Kafka’s normal replication and allows observers to tail the log.
2. **Quorum commit semantics** — commit = replicated to ⌈(N+1)/2⌉ voters, and the leader must have replicated at least one record from *its own* epoch before advancing the high watermark (prior-leader completeness).
3. **Epoch-aware log reconciliation** — instead of Raft-style `prevLogIndex/prevLogTerm`, the leader returns `DivergingEpoch` metadata in Fetch responses; the follower truncates to the diverging boundary and re-fetches.

## 2. Roles and state machine

Five states per node (four voting + one observer):

| State          | Who                                               | Behavior                                                                 |
|----------------|---------------------------------------------------|--------------------------------------------------------------------------|
| `Unattached`   | voter who has not yet voted or seen a leader      | awaits `BeginQuorumEpoch`, Fetch, or an election timeout                 |
| `Voted`        | voter who granted a Vote this epoch               | refuses to grant another vote in the same epoch                          |
| `Candidate`    | voter running an election                          | sends `Vote` to all voters, counts majority                              |
| `Follower`     | voter whose leader is known                        | sends `Fetch`, replicates records, restarts election on timeout          |
| `Leader`       | winner of the current epoch                        | handles Fetch from followers/observers, advances HW                      |
| `Observer`     | non-voting node (broker that isn't a controller)   | sends `Fetch`, never participates in elections                           |

Transitions follow standard Raft: any observed higher epoch forces demotion to `Unattached`; election timeouts promote to `Candidate`; majority vote yields `Leader`.

## 3. Wire protocol (new / extended RPCs)

Four new RPCs, plus extensions to Fetch and a new observability RPC. All messages use the standard Kafka request/response JSON schema format. Fields below use `int8/int16/int32/int64/string/bytes/array` per Kafka conventions.

### 3.1 VoteRequest / VoteResponse
```
VoteRequest:
  cluster_id: string
  topics: array of
    topic_name: string
    partitions: array of
      partition_index: int32
      candidate_epoch: int32
      candidate_id: int32
      last_offset_epoch: int32
      last_offset: int64

VoteResponse:
  error_code: int16
  topics: array of
    topic_name: string
    partitions: array of
      partition_index: int32
      error_code: int16
      leader_id: int32              # -1 if unknown
      leader_epoch: int32
      vote_granted: bool
```

Voters grant a vote iff (a) epoch strictly greater than locally observed, (b) not already voted in this epoch (or voted for the same candidate), and (c) candidate's `(last_offset_epoch, last_offset)` is lexicographically ≥ the voter's own latest.

### 3.2 BeginQuorumEpochRequest / Response
Announces a new leader once it wins the vote. Sent from leader to all other voters. Fields mirror VoteRequest but omit log-position data; receivers update `leader_id` and transition to `Follower`.

### 3.3 EndQuorumEpochRequest/Response
Used when the current leader steps down voluntarily (controlled shutdown, membership change). Body carries `preferredSuccessors` so voters can bias their election timers.

### 3.4 Fetch (extended with KIP-595 fields)
Existing Fetch RPC gains three optional fields:

* `CurrentLeaderEpoch` — rejected with `FENCED_LEADER_EPOCH` if stale.
* `LastFetchedEpoch` — follower reports the epoch of its local log tip.
* `OffsetOutOfRange` response carries a **truncation point** (`DivergingEpoch`) when the follower has diverged, triggering local log truncation before the next fetch.

### 3.5 DescribeQuorumRequest/Response
New admin RPC used by `kafka-metadata-quorum.sh`. Returns:

* Current `leader_id`, `leader_epoch`, `high_watermark`.
* For each voter: `replica_id`, `log_end_offset`, `last_fetch_timestamp`, `last_caught_up_timestamp`.
* For each observer: similar but flagged non-voter.

## 4. Commit rule

A record at offset `o` in leader epoch `e` is considered **committed** when:
1. A majority of voters (including the leader) have `o` in their log at epoch `e`, **and**
2. The leader has itself written at least one record in epoch `e` (this forces the "no silent commit of prior-term records" invariant from Raft §5.4.2).

The leader keeps a per-voter `log_end_offset` map (populated by their `Fetch` requests) and advances the cluster `high_watermark` accordingly.

## Implementation Scope

Create a new `raft` Gradle module containing:

1. **`KafkaRaftClient`** — event-driven core. Owns `QuorumState` plus per-state sub-classes (`UnattachedState`, `VotedState`, `FollowerState`, `CandidateState`, `LeaderState`). Processes inbound RPCs, drives election / heartbeat timers, replicates records via the pull-based `Fetch`.
2. **`QuorumState` + `FileBasedStateStore`** — persists `{currentEpoch, votedId, leaderId, applyingOffset}` to a state file inside the metadata log directory. Atomic write via temp-file-then-rename.
3. **RPC definitions** — add Vote/BeginQuorumEpoch/EndQuorumEpoch/DescribeQuorum request & response JSON schemas under the Kafka client common-message resources directory and regenerate auto-gen classes. Extend the existing `FetchRequest`/`FetchResponse` with the new quorum-specific fields but behind tagged-fields so wire compatibility is preserved.
4. **Log integration** — a `ReplicatedLog` interface backed by `KafkaMetadataLog`, a thin wrapper over an existing `Log` instance, exposing `appendAsLeader`, `appendAsFollower`, `truncateToEndOffset`, `readFrom`, `highWatermark`, `latestEpoch`, etc.
5. **Snapshotting interface** (implementation optional for this task but the interface must be wired). `SnapshotWriter`/`SnapshotReader` types and a `snapshottable` flag on `ReplicatedLog`.
6. **Config surface.** `RaftConfig` with all new properties defined in section 6 below; `KafkaConfig` must accept them and route them through.
7. **Metrics.** A `KafkaRaftMetrics` object exposing `current-leader`, `current-epoch`, `current-vote`, `log-end-offset`, `log-end-epoch`, `high-watermark`, `election-latency-avg`, `commit-latency-avg`, `fetch-records-rate`.
8. **CLI changes** — new `kafka-metadata-quorum.sh` that prints `DescribeQuorum` results. Integration points with the broker startup script so a broker can be started in either ZK or Raft mode depending on `process.roles`.

## Configuration keys

- `controller.quorum.voters` — comma-separated list `id@host:port`.
- `controller.quorum.election.timeout.ms` — base election timeout (default 1 000 ms).
- `controller.quorum.fetch.timeout.ms` — follower fetch timeout (default 2 000 ms).
- `controller.quorum.request.timeout.ms` — per-RPC timeout (default 2 000 ms).
- `controller.quorum.election.backoff.max.ms` — exponential backoff cap.
- `controller.quorum.retry.backoff.ms` — base retry backoff.
- `process.roles` — `broker`, `controller`, or `broker,controller` (the existing config is extended).

## Out of scope for this task

* Full migration from ZooKeeper (KIP-500 proper). Unit tests may assume a pure KRaft cluster.
* Snapshotting / log compaction of the metadata log (KIP-630).
* The controller itself (`QuorumController`, `MetadataCache` refactor, etc.). Only the raft plumbing is required.
* Language bindings outside the Kafka JVM codebase.

## Acceptance criteria

* the raft test target passes for every new and existing test.
* A three-node cluster started via a storage-format CLI command + the broker start CLI command with `process.roles=controller` elects a leader and replicates records.
* `kafka-metadata-quorum.sh --describe status` returns a coherent leader, epoch, and HWM.
* Follower catching up from empty log correctly aligns via `DivergingEpoch` reply without panicking.
* `VoteRequest`, `BeginQuorumEpochRequest`, `EndQuorumEpochRequest`, `DescribeQuorumRequest`, and the extended `FetchRequest`/`FetchResponse` are visible in `ApiKeys` and routed by `KafkaApis`.
