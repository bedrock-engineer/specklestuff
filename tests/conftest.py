from typing import Any

import pytest

from speckle_objects import revit_like


@pytest.fixture
def model() -> list[dict[str, Any]]:
    return revit_like()
