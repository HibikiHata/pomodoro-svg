# How it behaves, and why

A pomodoro timer as a static SVG has one hard question: **when does it start?** Every
other decision here follows from the answer.

## The timer starts when the image is painted

There is no server, no workflow, and no JavaScript — browsers disable scripting for SVG
loaded through `<img>`. The only clock available is the viewer's own animation clock,
which begins when their browser paints the file.

**So opening the page is what pressing "start" means.** Once that is accepted the timer
is exact: no delivery lag sits between the file and the display.

The alternative was to bake a negative `animation-delay` so the drawing tracked a
session started elsewhere, regenerating on a schedule. That cannot be accurate. The
animation's origin is the moment the viewer's browser paints the file, not the moment it
was generated, so the error equals the file's age at load: GitHub Actions' five-minute
cron minimum, plus its documented scheduling delays, plus `raw.githubusercontent.com`'s
five-minute cache. Five to fifteen minutes of error against a quantity that is itself
twenty-five minutes.

### What this costs

**Reloading the page restarts the timer.** That is the semantics, not a defect.

**A browser may reload the page without you doing anything.** Chrome's Memory Saver
proactively discards tabs that have been unused in the background for some time — not
only under memory pressure — and reloads them when you return. A discarded pomodoro
shows `25:00`, which is indistinguishable from one you just started. There is no way to
detect or recover from this inside the SVG, because that would need JavaScript.

If you want to be certain a session is intact, keep the tab visible, or add the page to
Chrome's "always keep these sites active" list.

## There is no pause

Collapsing a `<details>` block was the only mechanism a README offers, and it does not
suspend the animation — which is the same fact as a hidden tab continuing to advance.
The two cannot both be true, and "correct while you work in another window" is the one a
pomodoro needs.

Clicking the image, if you wrap it in a link to its own raw URL, opens the SVG on its own
and starts it from zero. That is the only click behaviour available.

## Measured on github.com

GitHub does not document how it renders SVG, so each of these came from putting a file
there and looking at it. Chrome, 2026-08.

| Behaviour | Result |
|---|---|
| The animation timeline advances while the tab is hidden | yes |
| Collapsing `<details>` pauses it | no |
| `<clipPath>` | works |
| `steps()` timing function | works |
| `@font-face` with a base64 data URI | works |
| `<view>` element via `#id` | does not work |
| `#svgView(viewBox(...))` | does not work |
| `:target` via `#id` | works |

The last three are the informative ones: the fragment *does* reach the document, but
Chrome does not implement view-based cropping for `<img>`-loaded SVG. That is why every
variant is a separate file rather than one file selected by a fragment.

Two things measured earlier still hold. Inline `<svg>` is stripped from Markdown, so
`<img>` is mandatory; and `prefers-color-scheme` inside the SVG resolves against the
operating system rather than GitHub's theme toggle, which is why light and dark are two
files rather than one.

**One media query resolving against the OS is exactly right.**
`prefers-reduced-motion` is a property of the viewer, not of the page, so the mechanism
that makes `prefers-color-scheme` useless here makes this one correct. Every animation
stops for viewers who ask for reduced motion, leaving a readable still.

## Why these four schedules

There is no single best interval, and any source that offers one is either generalising
from a sample of one or reading a correlation as a cause.

**25 minutes has no scientific derivation.** Francesco Cirillo, a student in the late
1980s, tried intervals from two minutes to an hour and settled on 25 for himself. The
technique's substance is the system around it — planning, interruption handling,
estimation — and its rules are about conduct, not duration.

The evidence is split. A 2025 study (*Behavioral Sciences* 15(7):861, N=94) found no
difference in task completion between Pomodoro, Flowtime and self-regulated breaks, but
did find fatigue rising and motivation falling faster under Pomodoro. A 2023 study in the
*British Journal of Educational Psychology* found no difference in mental effort. A 2025
scoping review reported 88% of studies positive — but it is limited to anatomy education,
most of its studies are observational, and its three randomised trials used 24/6 and
12/3 rather than 25/5.

Theory argues against 25 minutes for demanding work: reaching flow takes 15–30 minutes,
and the ultradian literature puts sustained performance in 90–120 minute cycles. DeskTime's
often-quoted 52/17 is a correlation in observational data, and the same company's later
analyses moved the number repeatedly.

So the shipped set covers the span instead of picking a winner.

| Schedule | Long break | For |
|---|---|---|
| 15/5 | 15 | Short attention spans |
| **25/5** | 15 | The canon |
| 50/10 | 20 | Everyday knowledge work |
| 90/20 | 30 | Deep work |

Any other combination is one command away — see the README.

## Determinism

The same options always produce the same bytes. Attribute order and float precision are
fixed, the font subset is built with its timestamps zeroed, and the matrix design's
falling columns take their periods from the column index rather than from a random
number. Regenerating never produces a diff that means nothing.
