"""Call a routed implementation for one fixed operation, filling omitted parameters with defaults."""

import inspect
from collections.abc import Callable
from typing import Any

from pydantic.fields import FieldInfo


def _default(param: inspect.Parameter) -> Any:
    default = param.default
    if isinstance(default, FieldInfo):
        if default.default_factory is not None:
            return default.default_factory()  # type: ignore[call-arg]
        return None if default.is_required() else default.default
    return None if default is inspect.Parameter.empty else default


async def call_routed(
    fn: Callable[..., Any], action: str, given: dict[str, Any]
) -> Any:
    """Run ``fn`` with ``action`` fixed; parameters the caller does not serve take their defaults."""
    values: dict[str, Any] = {}
    for name, param in inspect.signature(fn).parameters.items():
        if name == "action":
            values[name] = action
        elif name in given:
            values[name] = given[name]
        else:
            values[name] = _default(param)
    result = fn(**values)
    return await result if inspect.isawaitable(result) else result
