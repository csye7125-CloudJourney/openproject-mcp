# Kafka replay - `openproject.events.raw`

For when you need to replay OpenProject webhook events back into the in-memory
events cache, or just peek at what's sitting on MSK.

## Topology

```
OpenProject  --POST /webhooks/openproject-->  MCP ingest  --produce-->  MSK
                                                                          |
                                                                          v
                                                              MCP replay consumer
                                                                          |
                                                                          v
                                                              EventsCache (in-mem)
                                                                          |
                                                                          v
                                                          MCP tool get_recent_events
```

- Topic: `openproject.events.raw`
- Partitions: 12 (terraform-provisioned, `terraform/modules/msk`)
- Replication: 3, min.isr=2
- Retention: 7 days
- Consumer group: `openproject-mcp-replayer`
- Auth (prod): SASL_SSL + AWS_MSK_IAM via pod IRSA
- Auth (dev): PLAINTEXT against docker-compose kafka:9092

## When to replay

1. Cache was lost (pod restart, OOM, rollback) and you want the last 7d back
   in memory.
2. A consumer bug landed and you need to re-process from a known good offset.
3. You want to test a new schema mapping against historical traffic.

## Replay (in-cluster)

The consumer takes a `--from-beginning` flag that resets the group to
`auto.offset.reset=earliest`. In-cluster you can either:

### Option A: flip the env var on the existing Deployment

```bash
kubectl -n openproject-mcp set env deployment/openproject-mcp \
  MCP_KAFKA_FROM_BEGINNING=1
kubectl -n openproject-mcp rollout restart deployment/openproject-mcp
# watch records get consumed
kubectl -n openproject-mcp logs -l app=openproject-mcp -f | grep -i kafka
# once caught up, unset and roll forward
kubectl -n openproject-mcp set env deployment/openproject-mcp \
  MCP_KAFKA_FROM_BEGINNING-
kubectl -n openproject-mcp rollout restart deployment/openproject-mcp
```

### Option B: dedicated replay Job (preferred for big backfills)

`k8s/jobs/replay.yaml` runs the consumer module directly. Same image, same
IRSA role. Doesn't disturb the serving pod.

```bash
kubectl -n openproject-mcp create -f k8s/jobs/replay.yaml
kubectl -n openproject-mcp logs -f job/openproject-mcp-replay
```

## Inspecting the topic from a bastion (MSK-IAM)

Need `kafka_2.13-3.6.0/bin/` and the `aws-msk-iam-auth` jar on the
classpath. The bastion in `terraform/modules/bastion` ships both.

`/etc/kafka/client.properties`:

```properties
security.protocol=SASL_SSL
sasl.mechanism=AWS_MSK_IAM
sasl.jaas.config=software.amazon.msk.auth.iam.IAMLoginModule required;
sasl.client.callback.handler.class=software.amazon.msk.auth.iam.IAMClientCallbackHandler
```

```bash
export BOOTSTRAP=$(aws kafka get-bootstrap-brokers \
  --cluster-arn "$MSK_CLUSTER_ARN" \
  --query 'BootstrapBrokerStringSaslIam' --output text)

# tail the topic
kafka-console-consumer.sh \
  --bootstrap-server "$BOOTSTRAP" \
  --topic openproject.events.raw \
  --consumer.config /etc/kafka/client.properties \
  --from-beginning \
  --property print.key=true \
  --property key.separator=" | " \
  --max-messages 50

# list consumer groups + lag
kafka-consumer-groups.sh \
  --bootstrap-server "$BOOTSTRAP" \
  --command-config /etc/kafka/client.properties \
  --describe --group openproject-mcp-replayer
```

## Resetting consumer group offsets

To move the group back without flipping `auto.offset.reset` for everyone,
stop the consumer first then:

```bash
kafka-consumer-groups.sh \
  --bootstrap-server "$BOOTSTRAP" \
  --command-config /etc/kafka/client.properties \
  --group openproject-mcp-replayer \
  --topic openproject.events.raw \
  --reset-offsets --to-earliest --execute
```

`--to-datetime 2025-08-25T00:00:00.000` is the safer everyday variant when you
only want the last N hours back.

## Health checks

- Cache size: `kubectl exec` into the pod and `curl localhost:8080/metrics`;
  the `openproject_mcp_events_cache_size` gauge (added later) is the cheap
  proxy.
- Consumer lag: `kafka-consumer-groups.sh --describe` above. Alert at >10,000
  records sustained.
- HMAC reject rate: 401s on `/webhooks/openproject` mean the signing key rolled
  and a sender is still on the old one.

## Failure modes

| Symptom | Probable cause | Recovery |
|---------|----------------|----------|
| All webhooks return 503 `ingest not ready` | producer never started; lifespan failure | check pod logs for `kafka producer failed to start`, fix IAM / connectivity |
| Webhooks return 401 | HMAC mismatch | rotate / re-distribute `WEBHOOK_HMAC_SECRET` |
| Cache stays empty after produce works | consumer never started or stuck | `kubectl logs` for `kafka replay consumer started`; check IRSA `kafka-cluster:ReadData` |
| Same event id reappears repeatedly | consumer not committing | check `commit failed` log line; usually transient broker auth issue |
| Lag growing unbounded | partitions > consumer threads | scale Deployment replicas; partition count is 12 so up to 12 helps |
