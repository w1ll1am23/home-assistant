import logging

from pyeconet.equipment import EquipmentType
from pyeconet.equipment.thermostat import ThermostatOperationMode, ThermostatFanMode

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_AUX_HEAT,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)

from homeassistant.const import (
    ATTR_TEMPERATURE,
)

from .const import (
    EQUIPMENT
)

from . import EcoNetEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_BEEP_ENABLED = "beep_enabled"
ATTR_SCREEN_LOCKED = "screen_locked"

ECONET_STATE_TO_HA = {
    ThermostatOperationMode.HEATING: HVAC_MODE_HEAT,
    ThermostatOperationMode.COOLING: HVAC_MODE_COOL,
    ThermostatOperationMode.OFF: HVAC_MODE_OFF,
    ThermostatOperationMode.AUTO: HVAC_MODE_AUTO,
    ThermostatOperationMode.FAN_ONLY: HVAC_MODE_FAN_ONLY,
}
HA_STATE_TO_ECONET = {value: key for key, value in ECONET_STATE_TO_HA.items()}

# TODO: How to handle medlo and medhi
#    ThermostatFanMode.MEDHI: FAN_HIGH,
#    ThermostatFanMode.MEDLO: FAN_MEDIUM,
ECONET_FAN_STATE_TO_HA = {
    ThermostatFanMode.AUTO: FAN_AUTO,
    ThermostatFanMode.LOW: FAN_LOW,
    ThermostatFanMode.MEDIUM: FAN_MEDIUM,
    ThermostatFanMode.HIGH: FAN_HIGH
}
HA_FAN_STATE_TO_ECONET = {value: key for key, value in ECONET_FAN_STATE_TO_HA.items()}

SUPPORT_FLAGS_THERMOSTAT = (
        SUPPORT_TARGET_TEMPERATURE
        | SUPPORT_TARGET_TEMPERATURE_RANGE
        | SUPPORT_FAN_MODE
        | SUPPORT_AUX_HEAT
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up EcoNet thermostat based on a config entry."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    async_add_entities(
        [EcoNetThermostat(thermostat) for thermostat in equipment[EquipmentType.THERMOSTAT]],
    )


class EcoNetThermostat(EcoNetEntity, ClimateEntity):
    """Define a Econet thermostat."""

    def __init__(self, thermostat):
        """Initialize."""
        super().__init__(thermostat)
        self._running = thermostat.running
        self._poll = True
        self.thermostat = thermostat
        self.econet_state_to_ha = {}
        self.ha_state_to_econet = {}

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self.thermostat.supports_humidifier:
            return SUPPORT_FLAGS_THERMOSTAT | SUPPORT_TARGET_HUMIDITY
        else:
            return SUPPORT_FLAGS_THERMOSTAT

    @property
    def device_state_attributes(self):
        """Return the optional device state attributes."""
        _attr = super().device_state_attributes
        _attr[ATTR_BEEP_ENABLED] = self.thermostat.beep_enabled
        _attr[ATTR_SCREEN_LOCKED] = self.thermostat.screen_locked

        return _attr

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermostat.set_point

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self.thermostat.humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        if self.thermostat.supports_humidifier:
            return self.thermostat.dehumidifier_set_point
        else:
            return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_COOL:
            return self.thermostat.cool_set_point
        elif self.hvac_mode == HVAC_MODE_HEAT:
            return self.thermostat.heat_set_point
        else:
            return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return self.thermostat.heat_set_point
        else:
            return None

    @property
    def target_temperature_high(self):
        """Return the higher bound temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return self.thermostat.cool_set_point
        else:
            return None

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp:
            self.thermostat.set_set_point(target_temp, None, None)
        elif target_temp_low or target_temp_high:
            self.thermostat.set_set_point(None, target_temp_high, target_temp_low)
        else:
            _LOGGER.error("Something went wrong")

    @property
    def is_aux_heat(self):
        """Return true if aux heater."""
        return self.thermostat.mode == ThermostatOperationMode.EMERGENCY_HEAT

    @property
    def hvac_modes(self):
        """Return hvac operation ie. heat, cool mode.
        Need to be one of HVAC_MODE_*.
        """
        econet_modes = self.thermostat.modes
        op_list = []
        for mode in econet_modes:
            if mode not in [ThermostatOperationMode.UNKNOWN, ThermostatOperationMode.EMERGENCY_HEAT]:
                ha_mode = ECONET_STATE_TO_HA[mode]
                op_list.append(ha_mode)
        return op_list

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool, mode.

        Needs to be one of HVAC_MODE_*.
        """
        econet_mode = self.thermostat.mode
        _current_op = HVAC_MODE_OFF
        if econet_mode is not None:
            _current_op = ECONET_STATE_TO_HA[econet_mode]

        return _current_op

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode"""
        hvac_mode_to_set = HA_STATE_TO_ECONET.get(hvac_mode)
        self.thermostat.set_mode(hvac_mode_to_set)

    def set_humidity(self, humidity: int):
        """Set new target humidity."""
        self.thermostat.set_dehumidifier_set_point(humidity)

    @property
    def fan_mode(self):
        """Return the current fan mode"""
        econet_fan_mode = self.thermostat.fan_mode

        # Remove this after we figure out how to handle med lo and med hi
        if econet_fan_mode in [ThermostatFanMode.MEDHI, ThermostatFanMode.MEDLO]:
            econet_fan_mode = ThermostatFanMode.MEDIUM

        _current_fan_mode = FAN_AUTO
        if econet_fan_mode is not None:
            _current_fan_mode = ECONET_FAN_STATE_TO_HA[econet_fan_mode]
        return _current_fan_mode

    @property
    def fan_modes(self):
        """Return the fan modes."""
        econet_fan_modes = self.thermostat.fan_modes
        fan_list = []
        for mode in econet_fan_modes:
            # Remove the MEDLO MEDHI once we figure out how to handle it
            if mode not in [ThermostatFanMode.UNKNOWN, ThermostatFanMode.MEDLO, ThermostatFanMode.MEDHI]:
                fan_list.append(ECONET_FAN_STATE_TO_HA[mode])
        return fan_list

    def set_fan_mode(self, fan_mode):
        """Set the fan mode"""
        self.thermostat.set_fan_mode(HA_FAN_STATE_TO_ECONET[fan_mode])

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self.thermostat.set_mode(ThermostatOperationMode.EMERGENCY_HEAT)

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self.thermostat.set_mode(ThermostatOperationMode.HEATING)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.thermostat.set_point_limits[0]

    @property
    def max_temp(self):
        """Return the maximum temperature"""
        return self.thermostat.set_point_limits[1]

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return self.thermostat.dehumidifier_set_point_limits[0]

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return self.thermostat.dehumidifier_set_point_limits[1]