# contracts/

Shared. Changes require a `type:contract-change` issue acked by every consumer (see `docs/PROTOCOL.md`).

- `api/` - OpenAPI files, one per service (`data-platform.yaml`, `insights-sponsors.yaml`, `game-engine.yaml`). Contract-first: write the spec, then implement. Owners: the service's agent. Consumers: client agents and other services.
- `db/` - Tiger Data schema contract (tables, hypertables, continuous aggregates, migrations index). Owner: data-platform.
- `events/` - event shapes (e.g. check-in, rider_event, alert) as JSON Schema. Owner: whoever emits; consumers must ack.
