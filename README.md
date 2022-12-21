# OBS Replay Buffer Auto-Enable

**WORK IN PROGRESS**

Automatically enables the replay buffer when certain applications are launched.
The list of applications is configured in `replay-buffer-autoenable-config.json`.

## Installation

Copy `replay-buffer-autoenable.py` and `replay-buffer-autoenable-config.json`
into the following folder on your system (Windows):

```
C:\Program Files\obs-studio\data\obs-plugins\frontend-tools\scripts
```

Change the configuration file (JSON) to your liking,
by adding or removing application paths from the `"applications"` JSON key.
Make sure to put the full path of your application there.

## Configuration variables

> `check_frequency_seconds`  
How often to check if any of the mentioned applications are running, in seconds.

> `applications`  
A list of applications to check.
If one of them is running the replay buffer will be enabled.

> `disable_buffer_on_idle`  
Disables the replay buffer if none of the listed applications are running.

## Development

For ease of development add the following folder to your IDE's Python path:

```
C:\Program Files\obs-studio\data\obs-scripting\64bit
```

Proper configuration for Visual Studio Code can be found in the `.vscode` folder.

Scripting Cheatsheet: https://github.com/upgradeQ/OBS-Studio-Python-Scripting-Cheatsheet-obspython-Examples-of-API/blob/master/README.md

MP3 Voice lines in folder `replay-buffer-convenience` generated with https://freetts.com,
language "English (US)" and voice "Salli_Female".
