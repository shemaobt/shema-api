---
status: accepted
date: 2026-09-08
---

# `Range` stays in the bucket CORS allowlist; `PUT` and `x-goog-resumable` are out

The **Sound Necklace** single-page app only ever issues signed GET requests against its
bucket. Uploads travel through the API rather than a signed URL, so the write verb and the
resumable-upload header had no reason to sit in that allowlist, and were taken out.

`Range` stays, though not for the reason first written down. It is a CORS-safelisted request
header: the Fetch standard safelists it when the value parses as a single range with a
non-null start, which is what an ordinary seek sends, and requests like that never preflight.
What is not safelisted is a suffix range, the tail of a file, because browsers historically
never emitted one; those still preflight, and the bucket answers a preflight by echoing its
response-header allowlist into the allowed-headers field. That same field becomes the
exposed-headers list on simple requests, which is what lets a player read the content range and
the content length back. Keeping the header covers both paths and costs nothing.

Source: the Fetch standard, CORS-safelisted request-header
(https://fetch.spec.whatwg.org/#cors-safelisted-request-header).

The two CORS files are applied by hand and by nobody else — no workflow, script or startup
path reads them — so they can drift from the live buckets silently, and one of them already
had. Read the bucket before trusting the file.
