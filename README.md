# srt2otr
convert srt files to otr


.otr file format:

```
{
    "text": "<transcript with timecodes>",
    "media": "<audio/video file>",
    "media-time": <last timecode>
 }
```

`media` and `media-time` are optional.

The transcript is html.

Timecode format:

```
<span class=\"timestamp\" data-timestamp=\"seconds.decimals\">minutes:seconds</span>
```

