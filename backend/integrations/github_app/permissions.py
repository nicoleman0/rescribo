from collections.abc import Mapping

ISSUE_PERMISSIONS = {"issues": "write", "metadata": "read"}
RELEASE_PERMISSIONS = {"contents": "read", "metadata": "read"}
REQUIRED_INSTALLATION_PERMISSIONS = {"issues": "write", "metadata": "read"}
OPTIONAL_INSTALLATION_PERMISSIONS = {"contents": "read"}


def check_installation_permissions(permissions: object) -> bool:
    if not isinstance(permissions, Mapping):
        return False
    allowed = {**REQUIRED_INSTALLATION_PERMISSIONS, **OPTIONAL_INSTALLATION_PERMISSIONS}
    return all(
        permissions.get(key) == level for key, level in REQUIRED_INSTALLATION_PERMISSIONS.items()
    ) and all(key in allowed and allowed[key] == level for key, level in permissions.items())
