# Renamer

## Description

*Renamer* is a command-line tool for bringing a folder containing a digital music album to a certain standard. The script pulls information on a given album from Discogs, rewrites tags and renames files (Discogs user token is required: https://www.discogs.com/developers/#page:authentication).

When the script is run without extra options, a release will be picked based on the specified folder name and audio files contained therein.

`--catno` option can be added to search Discogs database by the release's catalogue number.

To eliminate ambiguous results, supplying the `--id` option is encouraged (found at the end of a release URL at Discogs, e.g. `https://www.discogs.com/<name-of-the-release>/release/<ID>`).

Adding `--list 1` option outputs release candidates based on the specified folder name (without any changes to the folder or the files). A release ID can then be chosen to be applied to the folder being renamed.

Adding `--debug 1` option outputs various details for debugging.

## Examples

Intended use: the folder is placed alongside the script file.

```
python3 renamer.py --folder "LSG-Netherworld_2005-Promo-CDR-2005-UTE"
python3 renamer.py --folder "Snap! - Rhythm Is A Dancer" --catno "665 309"
python3 renamer.py --folder "Stanley Foort - Heaven Is Here (Remixes)" --id "448625"
```

## TODO

* Allow user-specified renaming patterns
