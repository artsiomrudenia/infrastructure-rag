# Filesystem capacity exhaustion

## Symptoms
Writes fail with ENOSPC. The filesystem is full or has no free inodes.
This differs from slow storage with available space.

## Checks
1. Run df -h for capacity and df -i for inode usage.
2. Inspect log retention and abandoned temporary files.

## Typical fix
Remove disposable files according to retention policy or expand the filesystem.
