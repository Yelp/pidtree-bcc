# Roadmap
This outlines some things that we're hoping to target in the near future
## Plugin architecture
The core functionality of pidtree-bcc will work on a majority of Linux
systems, but we believe that the best signal-to-noise ratio and utility
metadata can be achieved by making your defensive systems reflect your
internal logic, so we will be introducing a plugin architecture to allow
you to enrich the process tree metadata with things that may not be
installed on all systems, for example
## Debian system package
Installing pidtree-bcc should be as simple as `apt install pidtree-bcc`
when pointing to a repository where the debian package is hosted. To do
this, we need to ensure that we have reliable package builds for all
dependencies, dependencies ensured in the debian control files and a
good package deploy workflow. Installing Linux kernel headers *for the
current running kernel* may be a challenge

The advantage of a debian package over Docker would be fewer moving
parts, no reliance on a container runtime and less configuration.
