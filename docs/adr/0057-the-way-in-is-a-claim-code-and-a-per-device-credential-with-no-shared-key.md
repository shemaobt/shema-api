---
status: accepted
date: 2026-10-09
---

# The way in is a claim code and a per-device credential, with no shared key

Two ways into the room stood side by side. A tablet could show a claim code, a facilitator
spent it from the Desk to link the tablet to a team, and the tablet then collected its own
device credential. Every installed app also carried the same shared room key, `X-Room-Key`,
and a request with no device credential was let in on it. A caller on the key named no
device and no team: its sessions belonged to nobody, it could read any live session by id,
and it could halt any claimed tablet. The key could not be revoked per tablet, only by
shipping a new app. ENG-1264 asked production to choose one way in.

Decided by Henok on 2026-10-09 (ENG-1518, server half of ENG-1264):

- Production keeps the claim code linked from the Desk and the device credential. The
  shared room key retires: no request is opened by it, and its setting is gone.
- A team door opens only to a device credential the tablet collected, of a device whose
  team still exists. The copy of the credential the claim hands the Desk opens no team door,
  and neither does the credential of a tablet whose team was deleted. Both are refused
  exactly like a credential nobody issued. A revoked credential keeps its own refusal, so the
  tablet knows to forget it and show a new claim code.
- The three doors a tablet calls before it belongs to a team open to anyone, with no header:
  minting a claim code, reading whether it was spent, and collecting the credential. The
  device id is minted by the server, a claim code is only worth what a facilitator spends on
  it, and the credential is collected once.
- With every caller in a team, a session read is scoped to the caller's team, and a turn
  replay is too. A session that names no team is reached by no tablet.

Rejected:

- Marcia's typed team code: one code per team, typed once on a locked screen and remembered
  by the tablet. It is a shared secret again, one per team instead of one per deployment, and
  revoking one tablet would mean changing the code for every tablet of its team. The claim
  code and the Desk's link already exist and revoke one tablet at a time.
- Keeping the key beside the credential while tablets in the field move over. The key
  was what let a caller name no team, and every scoping rule above depends on there being none.

Consequences:

- A tablet in the field must hold a collected credential before an app without the key is
  installed on it; the app's half is ENG-1519.
- Sessions opened on the key in the past name no team and are now unreachable. The app drops
  a session the server no longer has and opens a fresh one, so a team loses its place in such
  a session, not its recordings, which stay in the database.
- The deploy workflows still bind the `INTERNALIZATION_ROOM_API_KEY` secret. Nothing reads it.
  Removing that line is left to Henok.
