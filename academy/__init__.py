"""Academy — the reusable, tenant-scoped training app (ARCHITECTURE.md §4).

This package never imports the host or ``host_stub`` (gate G7): host seams are reached only
through ``academy.adapters.loader``, and users appear as opaque ``user_ref`` strings.
"""
