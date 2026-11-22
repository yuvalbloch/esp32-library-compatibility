# Contributing

Thanks for helping make the table more useful. Most contributions need no code.

## Ask for a library to be added

Open an [“Add a library” issue](../../issues/new?template=add-library.yml) with the library's name exactly as it appears in the Arduino Library Manager. Libraries are added in waves, ordered by [popularity and breakage risk](docs/library-selection.md). Libraries with many requests move up.

## A library was fixed

New releases of tracked libraries are picked up automatically within a day: the daily job compiles every new version. If a fix needs a recheck sooner, or the fix is in a core release, open a [“Recheck” issue](../../issues/new?template=recheck.yml).

Old results are never removed. The fixed version gets its own new row, and the pin tool will recommend it.

## A result looks wrong

Open a [“Wrong result” issue](../../issues/new?template=wrong-result.yml) and include:

- the link to the compile log (click the cell in the table, then “compile log”)
- what you expected, and why (e.g. "this example builds for me with arduino-cli 1.6.0 and core 4.0.0")

Typical causes worth reporting:

- the example we picked is not representative (e.g. it targets a specific board)
- a needed library was not added, so the log shows `No such file or directory`
- the wrong library was added for a missing header

We fix the farm, never the result: the cell is recompiled, and the new log decides.

## Maintainers: badge

A compatibility badge for your README is planned. Watch this repository for it.

## Code contributions

The farm is in [`farm/`](farm/) (Python 3.11, standard library only) and the website in [`site/`](site/) (static HTML/JS, no build step). See [docs/running-the-farm.md](docs/running-the-farm.md).

- Changes to the status rules in [`farm/classify.py`](farm/classify.py) must keep the core rule: exit code 0 is always `pass` and a non-zero exit is never `pass`. Explain any change in the pull request with example logs.
- Better example picks go in [`farm/examples_override.json`](farm/examples_override.json).
