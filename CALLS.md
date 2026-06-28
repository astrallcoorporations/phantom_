# Calls

Voice/video calls **work out of the box — no setup, no credentials, no TURN server.**

Phantom routes calls through **Jitsi's free public infrastructure** (`meet.jit.si`).
Jitsi runs its own media servers and STUN/TURN, so it handles NAT traversal for
you — including the hard cases (mobile data / carrier-grade NAT / strict
firewalls) that plain peer-to-peer WebRTC can't cross without a paid TURN relay.

How it works:
- Each conversation maps to a deterministic, opaque Jitsi room name, so both
  people land in the same room.
- Phantom only sends the "ring" (incoming-call notification) over Supabase
  Realtime; pressing **Answer** joins the same room.
- Calls are encrypted in transit (DTLS-SRTP). The 90-minute cap and the
  voice/video toggle still apply.

There's nothing to configure. The old TURN env vars (`CF_TURN_*`, `METERED_*`)
are no longer used by calling and can be ignored.
