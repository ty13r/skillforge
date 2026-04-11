# elixir-phoenix-channel

**Rank**: #16 of 22
**Tier**: E (brainstormed runner-up; no research signal)
**Taxonomy path**: `development` / `phoenix-framework` / `elixir`
**Status**: Brainstormed; LiveView has replaced most uses

## Specialization

Writes Phoenix Channel modules with `use Phoenix.Channel`, `join/3` lifecycle, `handle_in/3` message routing, `Phoenix.Presence` integration, broadcast patterns, and JS client integration via `phoenix.js`.

## Why this family is here

Phoenix Channels were the original real-time primitive in Phoenix. LiveView has replaced most use cases for them in modern Phoenix apps, but they're still relevant for:
- Native mobile clients (iOS/Android) talking to a Phoenix backend
- Custom protocols where LiveView's HTTP-over-WebSocket model doesn't fit
- High-throughput message-passing between clients

The research found **no specific Channel-related Claude failures**. Lower priority than LiveView family.

## Decomposition

### Foundation
- **F: `channel-architecture`** — Flat vs nested topics, socket-per-feature, single-vs-multi-channel apps

### Capabilities
1. **C: `channel-module-structure`** — `use Phoenix.Channel`, `join/3`, `handle_in/3`, `terminate/2`
2. **C: `topic-routing`** — `channel "room:*"` patterns, dynamic topics, topic authorization
3. **C: `join-and-auth`** — `join/3` authorization, socket assigns from initial connection
4. **C: `handle-in-patterns`** — Message type routing, reply shapes
5. **C: `presence`** — `Phoenix.Presence`, tracking, diffing, `handle_metas/4`
6. **C: `broadcast-patterns`** — `broadcast/3`, `broadcast_from/4`, server-initiated pushes
7. **C: `socket-state`** — Socket assigns vs separate process state
8. **C: `client-integration-js`** — `phoenix.js` channel client patterns
9. **C: `channel-testing`** — `Phoenix.ChannelTest`, `push/3`, `assert_reply/3`

### Total dimensions
**10** = 1 foundation + 9 capabilities

## Notes

- Lower priority than LiveView. Build only after the Tier S/A roster ships.
- Could merge with LiveView family as a "phoenix-realtime" mega-family, but their evaluation patterns are quite different.
