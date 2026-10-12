import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from automation.human_emulator import HumanEmulator, KEYBOARD_NEIGHBORS


@pytest.mark.asyncio
async def test_natural_pause():
    start = asyncio.get_event_loop().time()
    await HumanEmulator.natural_pause(0.05, 0.1)
    duration = asyncio.get_event_loop().time() - start
    assert duration >= 0.04


def test_keyboard_neighbors_mapping():
    assert "a" in KEYBOARD_NEIGHBORS
    assert "e" in KEYBOARD_NEIGHBORS
    assert KEYBOARD_NEIGHBORS["a"] == "s"


@pytest.mark.asyncio
async def test_human_type_simulation():
    mock_locator = AsyncMock()
    mock_locator.focus = AsyncMock()
    mock_locator.press_sequentially = AsyncMock()
    mock_locator.press = AsyncMock()

    await HumanEmulator.human_type(
        mock_locator,
        "RFID",
        min_delay_ms=1,
        max_delay_ms=5,
        typo_rate=0.0,
    )

    mock_locator.focus.assert_awaited_once()
    assert mock_locator.press_sequentially.await_count == 4


@pytest.mark.asyncio
async def test_human_click_simulation():
    mock_page = MagicMock()
    mock_page.mouse = MagicMock()
    mock_page.mouse.move = AsyncMock()

    mock_locator = AsyncMock()
    mock_locator.bounding_box = AsyncMock(return_value={"x": 100, "y": 150, "width": 80, "height": 30})
    mock_locator.click = AsyncMock()

    await HumanEmulator.human_click(mock_page, mock_locator)
    mock_page.mouse.move.assert_awaited_once()
    mock_locator.click.assert_awaited_once()
