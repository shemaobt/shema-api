---
status: accepted
date: 2026-10-20
---

# Takes download under her file names through links that last an hour

In her app a facilitator saves each rehearsal take as `<release>-<key>.<ext>` and each replaced
one as `<release>-<key>-substituida-<take id>.<ext>`, through links signed for an hour
(`src/draft/export.ts`, `retroExport.ts`, `supabaseStore.ts` at her freeze 18fa7c4). Ours
signed every take for fifteen minutes, named a download by the last segment of its storage key
(`tomada.m4a` for all), and listed no take apart from the part it was replaced by.

Decided (ENG-1283):

- `GET /facilitator/sessions/{session_id}/takes/downloads`, for a facilitator of the team or a
  consultant (ADR 0058), is the download door. It lists the **Part**s apart from the **Superseded
  take**s, each with its **Part key**, length, size, fingerprint and a link, and says the links
  last `links_valid_for_s: 3600`. The links are signed when the list is read, as her page's are;
  read it again for fresh ones.
- A live take downloads as `<release_id>-<key>.<ext>`, a superseded one as
  `<release_id>-<key>-substituida-<take id>.<ext>`. The **Part key** is `whole` for a part with no
  number and `S<n>` for the n-th current part in reading order; a superseded take takes the key
  of the part under its number. `<ext>` is ADR 0048's one rule: `wav`, else `m4a`.
- `<release_id>` is the passage's latest release as its stored packet names it: her name since
  ADR 0048, the row's uuid for releases stored before it. With no release yet it is the name
  version 1 will have, so the list is never refused for want of one.
- The name is signed into the link as a `Content-Disposition: attachment` that storage serves; the
  API never proxies the bytes. The shared signer takes an optional `response_disposition`.
- `superseded_at` is when the take that replaced it reached the server (its `created_at`), as her
  `supersededAt`, and never the tablet's **Recording time**.
- Only rehearsal takes with bytes are listed: a telling-back's take and a part the text seam
  declared are not files for Refine.
- Listen links, the tablet's list, the consultant's read, the packet and the stored objects'
  names do not change.

Rejected: **changing `/facilitator/takes/{take_id}/audio`**, because the consultant's play and the
retroverification file go through it and a browser cannot send the login on a plain link;
**proxying the bytes with the header from the API**, because storage serves the bytes; **her `mp4`
extension**, because ADR 0048 names compressed takes `.m4a`.

Consequences: a leaked link works for an hour, four times longer than any other link the room
signs. A list read before an approval names its files after the version before it until it is
read again, so Refine matches by take id and sha256 and never by the name. A take recorded after an approval downloads under the approved version's name until the next approval, as in her app (`releaseIdFor` is `max(1, finalizeCount)`); Refine's guard is the take's id and sha256, never the name, and the draft's badge (ENG-1235) and the Desk's row (ENG-1298) say that a draft is no longer approved as it stands. Takes already stored
download under the new names with their bytes untouched. The name is the passage's, as the
version is: a release another conversation of the same passage minted names this session's files.
