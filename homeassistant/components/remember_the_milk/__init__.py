"""The Remember The Milk integration."""

from dataclasses import dataclass

from aiortm import AioRTMClient, Auth, AuthError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SHARED_SECRET, DOMAIN, LOGGER
from .entity import RememberTheMilkEntity
from .storage import RememberTheMilkConfiguration

RTM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SHARED_SECRET): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [RTM_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

SERVICE_CREATE_TASK = "create_task"
SERVICE_COMPLETE_TASK = "complete_task"

SERVICE_SCHEMA_CREATE_TASK = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Optional(CONF_ID): cv.string}
)

SERVICE_SCHEMA_COMPLETE_TASK = vol.Schema({vol.Required(CONF_ID): cv.string})

DATA_COMPONENT = "component"
DATA_STORAGE = "storage"

type RememberTheMilkConfigEntry = ConfigEntry[RememberTheMilkData]


@dataclass
class RememberTheMilkData:
    """Runtime data for a Remember The Milk config entry."""

    entity_id: str


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Remember the milk component."""
    # pylint: disable-next=home-assistant-use-runtime-data
    hass.data[DOMAIN] = {}
    # pylint: disable-next=home-assistant-use-runtime-data
    hass.data[DOMAIN][DATA_COMPONENT] = EntityComponent[RememberTheMilkEntity](
        LOGGER, DOMAIN, hass
    )
    # pylint: disable-next=home-assistant-use-runtime-data
    storage = hass.data[DOMAIN][DATA_STORAGE] = RememberTheMilkConfiguration(hass)
    await hass.async_add_executor_job(storage.setup)
    if DOMAIN not in config:
        return True
    for rtm_config in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=rtm_config,
            )
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: RememberTheMilkConfigEntry
) -> bool:
    """Set up Remember The Milk from a config entry."""
    # pylint: disable-next=home-assistant-use-runtime-data
    component: EntityComponent[RememberTheMilkEntity] = hass.data[DOMAIN][
        DATA_COMPONENT
    ]
    # pylint: disable-next=home-assistant-use-runtime-data
    storage: RememberTheMilkConfiguration = hass.data[DOMAIN][DATA_STORAGE]

    rtm_config = entry.data
    account_name: str = rtm_config[CONF_USERNAME]
    LOGGER.debug("Adding Remember the milk account %s", account_name)
    api_key: str = rtm_config[CONF_API_KEY]
    shared_secret: str = rtm_config[CONF_SHARED_SECRET]
    token: str | None = rtm_config[CONF_TOKEN]  # None if imported from YAML
    client = AioRTMClient(
        Auth(
            client_session=async_get_clientsession(hass),
            api_key=api_key,
            shared_secret=shared_secret,
            auth_token=token,
            permission="delete",
        )
    )

    token_valid = True
    try:
        await client.rtm.api.check_token()
    except AuthError as err:
        token_valid = False
        if entry.source == SOURCE_IMPORT:
            raise ConfigEntryAuthFailed("Missing token") from err

    # The entity will be deprecated when a todo platform is added.
    entity = RememberTheMilkEntity(
        name=account_name,
        client=client,
        config_entry_id=entry.entry_id,
        storage=storage,
        token_valid=token_valid,
    )
    await component.async_add_entities([entity])
    entry.runtime_data = RememberTheMilkData(entity_id=entity.entity_id)

    # The services are registered here for now because they need the account name.
    # The services will be deprecated when a todo platform is added.
    # pylint: disable=home-assistant-service-registered-in-setup-entry
    hass.services.async_register(
        DOMAIN,
        f"{account_name}_create_task",
        entity.create_task,
        schema=SERVICE_SCHEMA_CREATE_TASK,
    )
    hass.services.async_register(
        DOMAIN,
        f"{account_name}_complete_task",
        entity.complete_task,
        schema=SERVICE_SCHEMA_COMPLETE_TASK,
    )

    if not token_valid:
        raise ConfigEntryAuthFailed("Invalid token")

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RememberTheMilkConfigEntry
) -> bool:
    """Unload a config entry."""
    component: EntityComponent[RememberTheMilkEntity] = hass.data[DOMAIN][
        DATA_COMPONENT
    ]
    await component.async_remove_entity(entry.runtime_data.entity_id)
    return True
