"""Generate the Flyway Java migration class."""

from __future__ import annotations

_TEMPLATE = """\
package {package};

import eu.ncdc.arizona.migration.task.LoadFromFileMigrationTask;

public class {class_name} extends LoadFromFileMigrationTask {{
}}
"""

_MODULE_PACKAGE = {
    "ams-rule": "eu.ncdc.arizona.rule.db.migration",
    "ams-policy": "eu.ncdc.arizona.policy.db.migration",
}


def generate(class_name: str, module: str) -> str:
    package = _MODULE_PACKAGE.get(module)
    if package is None:
        raise ValueError(
            f"Unknown module '{module}'. Known modules: {list(_MODULE_PACKAGE)}"
        )
    return _TEMPLATE.format(package=package, class_name=class_name)
