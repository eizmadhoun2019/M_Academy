#!/bin/sh
# Compile the Arabic catalogue before the command runs. The tracked source is the `.po` file;
# the development profile bind-mounts the repository, so an image-time copy would be shadowed.
set -e
if [ -d locale ]; then
  python scripts/compile_messages.py locale/ar
fi
exec "$@"
