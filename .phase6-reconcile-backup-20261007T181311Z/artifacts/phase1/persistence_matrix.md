# FRACTAL FLOW — PHASE 1 PERSISTENCE MATRIX

| Object | Storage | Durability Protocol | Identity | Snapshot Behavior | Journal Behavior | Recovery Behavior | Reconciliation Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tick** | Event Journal | Atomic write + fsync | SHA-256 fingerprint | Aggregated into bar snapshot | Appended as `TickReceived` | Replayed from journal tail | Stream validation |
| **Bar** | Event Journal / Snapshot | Atomic write + fsync | SHA-256 fingerprint | Checkpointed in AggregateSnapshot | Appended as `BarAggregated` | Restored from latest snapshot + tail replay | Timeframe gap detection |
| **DataQualityAssessment** | Event Journal / Envelope | Atomic write + fsync | StateEnvelope state_id | Checkpointed in AggregateSnapshot | Appended as `DataQualityEvaluated` | Restored from snapshot + tail replay | Re-evaluated on restart |
| **VolatilityMetrics** | Event Journal / Envelope | Atomic write + fsync | StateEnvelope state_id | Checkpointed in AggregateSnapshot | Appended as `VolatilityEvaluated` | Restored from snapshot + tail replay | Re-computed on bar replay |
| **StructureTransitionRecord** | Event Journal / Envelope | Atomic write + fsync | StateEnvelope state_id | Checkpointed in AggregateSnapshot | Appended as `StructureTransitioned` | Restored from snapshot + tail replay | Structural level re-validation |
