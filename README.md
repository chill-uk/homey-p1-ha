# Homey P1 for Home Assistant

This repository contains a custom Home Assistant integration that connects to a Homey Energy Dongle over its local WebSocket API and exposes common DSMR readings as sensors.

## HACS

This repository is structured for use as a HACS custom repository.

1. In HACS, add `https://github.com/chill-uk/homey-p1-ha` as an `Integration` repository.
2. Install `Homey P1`.
3. Restart Home Assistant.
4. Add the integration from `Settings -> Devices & Services`.

For versioned installs and upgrades in HACS, create GitHub releases such as `v0.1.0`. If there are no releases yet, HACS will install from the default branch instead.

## Configuration

After the integration is added, you can update the Homey Energy Dongle IP address from the integration options instead of removing and re-adding the integration.

## What it does

- Connects to `ws://<homey-p1-ip>/ws`
- Reconnects automatically if the socket drops
- Parses common DSMR telegram fields
- Creates Home Assistant sensors for energy, power, gas, voltage, current, and a few diagnostic counters

## Current scope

This first version is focused on unencrypted DSMR telegrams, which matches the `node-dsmr-parser` WebSocket example when you run it in `dsmr` mode without a decryption key.

## Install

1. Copy `custom_components/homey_p1` into your Home Assistant config directory.
2. Restart Home Assistant.
3. In the Homey app, enable the Homey Energy Dongle Local API.
4. Note the dongle IP address from the Homey app.
5. In Home Assistant, add the `Homey P1` integration and enter the dongle IP.

## Notes

- The Homey Energy Dongle must be reachable from Home Assistant on your local network.
- The Homey Energy Dongle only allows a limited number of WebSocket clients at the same time.
- If your meter requires decryption or uses DLMS framing, this integration will need an additional parser step.
