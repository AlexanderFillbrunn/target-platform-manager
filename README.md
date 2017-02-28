# target-platform-manager
Python script that manages a local mirror of a target platform.


## How to Use

### Configuration Files

`~/.target-platform/account`

Contains the username (line 1) and password (line 2) used for basic auth.

`~/target-platform/urls`

Contains the names and URLs (format: 'name : url') to the target platform sites (one per line).

### Commands

`python target-platform.py update tp1`

Downloads a new copy of the target platform tp1 under the configured URL. The current target platform is saved as a backup (if a backup is not already present).

`python target-platform.py restore tp1`

Restores the previous target platform for tp1, deleting the current one.

`python target-platform.py clean tp1`

Deletes the previous backup for tp1.

### Eclipse Configuration

1. In the Eclipse Preferences got to Plug-in Development → Target Platform.
2. Add an empty target platform.
3. Add a software site pointing to the location `~/.target-platform/current/<target-platform-name>` and install the desired features.
