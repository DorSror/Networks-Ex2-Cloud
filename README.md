# File Backup System (Server + Client)
 A simple file backing up system, composed of a server script and a client script.
 Allows backing up of directories onto the server and their recoveries.

## Featueres:
1. Backing up a directory and its contents (recursively).
2. Updates the server at each data change event (create/move/update/delete of a file/directory).
3. On first connect, allows you to choose a file to back up. On multiple logins, downloads the backed up directory to the client.
-- Works primarily on Linux but can be easily modified to function on windows (switch / characters with \ when necessary).

## Tools:
1. The connections are TCP based.
2. Uses the Watchdog python library.
