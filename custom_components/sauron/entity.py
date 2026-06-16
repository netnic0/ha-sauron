"""Base entity class for SAURon meter entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SUBSCRIPTION_ID, DOMAIN

if TYPE_CHECKING := False:
    from .coordinator import SauronCoordinator


class SauronMeterEntity(CoordinatorEntity["SauronCoordinator"]):
    """Base class for all SAURon entities tied to a water meter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: "SauronCoordinator",
        translation_key: str,
    ) -> None:
        super().__init__(coordinator)
        subscription_id = coordinator.config_entry.data[CONF_SUBSCRIPTION_ID]
        self._attr_unique_id = f"{subscription_id}_{translation_key}"
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subscription_id)},
            name="SAUR Water Meter",
            manufacturer="SAUR",
            model="Smart Meter",
            configuration_url="https://mon-espace.saurclient.fr",
        )
