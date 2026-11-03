---
status: accepted
date: 2026-10-28
---

# The whole passage is built once under a key fixed by the release and the takes

ENG-1284. Marcia's app hands Refine the passage as one file, `<release id>-inteira.wav`, when
every take is WAV. No join of audio existed here, and a join made on every read would keep
re-reading minutes of audio and could hand Refine two different files for one approval.

Decided (Henok, 2026-10-26): the file lives in storage under
`internalization-room/whole/<release id>/<sha256 of the live takes' sha256s in order>.wav`, with no
column on the release. A key that exists is served and never rebuilt; a re-recorded take or a new
version makes a new key; no file is ever deleted. Storage's write-once put makes two builds racing
for one key harmless.

The key is a promise to files already in the bucket, so its layout does not change. The take
downloads list and the manifest carry the route's path, never a signed link, so reading them builds
nothing; the route reads every take's own header, and one that is not 16 kHz mono 16-bit PCM
answers 409 `NOT_ALL_WAV` whatever its content type says. Only the route can know that, so the list
and the manifest offer the whole on the content types alone, as her app does.
