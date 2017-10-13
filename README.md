# Renamer

## Description

*Renamer* is a command-line tool for bringing a folder containing a digital music album to a certain standard. The script pulls information on a given album from Discogs, rewrites tags and renames files (Discogs user token is required: https://www.discogs.com/developers/#page:authentication).

To eliminate ambiguous results, supplying the `--id` option is encouraged (found at the end of a release URL at Discogs, e.g. `https://www.discogs.com/<name-of-the-release>/release/<ID>`).

## Examples

Intended use: the folder is placed alongside the script file.

```
python3 renamer.py --folder "James Dymond - Maze Runners"
python3 renamer.py --folder "James Dymond - Maze Runners" --catno "FSOE237A"
python3 renamer.py --folder "James Dymond - Maze Runners" --id "10388189"
```

## TODO

* Allow user-specified renaming patterns
