---
status: accepted
date: 2026-10-07
---

# A replaced recording gets a new object name, and confirm-upload checks it first

The Oral Collector's bucket is public and its objects carry no Cache-Control, so Cloud
Storage serves them as `public, max-age=3600`. Every upload of a recording went to the same
object name, so a replacement wrote over an object the cache kept serving for up to an hour.
Measured on the emulator during PR #247: the bucket held the new 7 s cut, and a download
minutes later got the original 10 s back, byte for byte. A second edit made on that stale
audio uploaded it over the right audio. Gain-only edits had done the same since ENG-402, and
so had the cleaning job. ENG-1482 sets the rule: audio the server already holds is never
written over.

- A recording's first upload keeps the name it always had, `{recording_id}{ext}`. A
  replacement goes to `{recording_id}-{uuid4 hex}{ext}`, a name that recording never used, so
  the recording's URL changes and no cached copy answers for it. Existing rows do not
  migrate.
- The name handed out is kept on the recording as its **pending object** until
  confirm-upload accepts it. Asking again for a URL in the same format returns the same
  name, so a resumed upload and the confirm agree. Asking in another format gets a fresh
  name, and the earlier pending object is deleted. A pending name equal to the one the
  recording already publishes is never handed out, since the upload would write over it.
- confirm-upload checks the object before it answers: it must exist, have the declared
  size, and match the md5 and crc32c when the app sends them. On success it publishes the
  name as `gcs_url` with status `uploaded`, commits, and only then deletes the previous
  object. A missing previous object is not an error (ADR 0029's inherited staging rows),
  and no failed delete fails the confirm, because the new audio is already published. On
  failure it answers 400 with a reason code, `UPLOAD_OBJECT_MISSING`,
  `UPLOAD_SIZE_MISMATCH` or `UPLOAD_CHECKSUM_MISMATCH`, and changes nothing: the upload
  status, the URL, the audio behind it and the pending object stay as they were. First
  uploads and replacements behave the same. With no pending object, the name in the recording's URL is checked (a repeated
  confirm); with no URL either, the first-upload name is checked (an upload started before
  this change).
- A replacement's upload URL leaves the upload status as it is; `uploading` and
  `upload_failed` keep meaning a first upload. So the stalled-upload sweep, the 180-day purge
  and «clear stale recordings» never reach a recording with published audio. A replacement
  that is never confirmed leaves its pending object in the bucket, a known gap accepted on
  the ticket.
- `process-upload` keeps only the verified status and its notification. It no longer writes
  the URL and no longer marks a failure, since a failure there would flag audio that is
  already published. It never marks verified, or tells the user to free device storage, for
  a recording that is not `uploaded`. The exception is a confirm the previous code queued
  before the deploy: that row is still `uploading` with no pending object, so the job runs
  confirm-upload's check and publish itself in the same run; refused, the row keeps its
  status and the user is told to keep the local recording.
- The cleaning job writes the cleaned audio under a new name chosen in a memoized step. It
  keeps the backup copy as before, points the recording at the new name, and then deletes the
  previous object; the backup keeps it recoverable. It repoints only while the recording's
  URL is still the one it cleaned. If a replacement was confirmed in the meantime, it deletes
  its cleaned object, leaves the URL alone and sets the cleaning status back to none.

Consequence: a split that downloads the recording's audio while a replacement or a cleaning
deletes the previous object now fails with a 404 and can be asked again. Before, it split the
old audio without saying so.

Rejected: `Cache-Control: no-store` on every upload. On the small signed PUT the header has
to be part of the signature, so the app would have to send it, which breaks app versions
already in the field. Entries cached before the deploy would also stay stale for up to an
hour. Keeping the check asynchronous was also rejected: the app hears "ok", deletes its local
file, and never learns that the check failed.
