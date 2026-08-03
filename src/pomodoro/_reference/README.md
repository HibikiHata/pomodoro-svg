# Reference

`original-pomodoro.svg` is the widget this project grew out of — a hand-written SVG
that animated a 25-minute countdown ring with `animation: countdown 1500s linear
forwards`. The `ring` and `minimal` designs reproduce its proportions (r=90, 8px
stroke) and its wording (`FOCUS`, `25 MIN`).

It is kept for reference only. Nothing imports it, and it is not shipped.

**Two things were changed rather than copied.**

It placed `FOCUS`, `25 MIN` and `FINISHED` at the same centre, each with its own
animation, so at the end all three overlapped into an unreadable stack. Here every
line's candidates are mutually exclusive by opacity, and the finished state drops the
duration line entirely.

Its `<title>` carried the name of the private repository it came from; that is the
only edit made to the file.

It named a system font stack, so its appearance depended on the viewer's machine. This
project embeds a subset instead.
