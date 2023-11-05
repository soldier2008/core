"""Test the Remember The Milk integration."""

from unittest.mock import MagicMock

from aiortm import AuthError
import pytest

from homeassistant.components.remember_the_milk.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import CREATE_ENTRY_DATA

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("storage")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading a config entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("ignore_missing_translations", [[]])
@pytest.mark.usefixtures("storage")
async def test_imported_config_entry_missing_token(
    hass: HomeAssistant,
    client: MagicMock,
) -> None:
    """Test an imported config entry that hasn't been re-authenticated yet.

    An entry imported from YAML has no token, so the token check fails and a
    reauth flow is started.
    """
    client.rtm.api.check_token.side_effect = AuthError("Invalid token!")
    config_entry = MockConfigEntry(
        data={**CREATE_ENTRY_DATA, "token": None},
        domain=DOMAIN,
        source=SOURCE_IMPORT,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
