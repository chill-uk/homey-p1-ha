# Homey P1 for Home Assistant

[![GitHub release](https://img.shields.io/github/release/chill-uk/homey-p1-ha?include_prereleases=&sort=semver&color=blue)](https://github.com/chill-uk/homey-p1-ha/releases/)
[![issues - homey-p1-ha](https://img.shields.io/github/issues/chill-uk/homey-p1-ha)](https://github.com/chill-uk/homey-p1-ha/issues)
[![GH-code-size](https://img.shields.io/github/languages/code-size/chill-uk/homey-p1-ha?color=red)](https://github.com/chill-uk/homey-p1-ha)
[![GH-last-commit](https://img.shields.io/github/last-commit/chill-uk/homey-p1-ha?style=flat-square)](https://github.com/chill-uk/homey-p1-ha/commits/main)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validation](https://github.com/chill-uk/homey-p1-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/chill-uk/homey-p1-ha/actions/workflows/validate.yml)

This repository contains a custom Home Assistant integration that connects to a Homey Energy Dongle over its local WebSocket API and exposes common DSMR readings as sensors.

Parts of the implementation were inspired by the `homey-energy-dongle-ws.js` example from
[athombv/node-dsmr-parser](https://github.com/athombv/node-dsmr-parser/blob/master/examples/homey-energy-dongle-ws.js).

## Installation

### HACS installation

The quickest way to install this integration is via [HACS](https://github.com/hacs/integration) by clicking the button below:

[![Add to HACS via My Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=chill-uk&repository=homey-p1-ha&category=integration)

1. Click the button above to add this repository to HACS as a custom integration.
2. Install `Homey P1` from HACS.
3. Restart Home Assistant.
4. In Home Assistant, go to `Settings -> Devices & Services`.
5. Add the `Homey P1` integration.

For versioned installs and upgrades in HACS, create GitHub releases such as `v0.1.0`. If there are no releases yet, HACS will install from the default branch instead.

### Manual installation

1. Copy `custom_components/homey_p1` into your Home Assistant config directory.
2. Restart Home Assistant.
3. In Home Assistant, add the `Homey P1` integration from `Settings -> Devices & Services`.

## Enabling Local API (requirement)

1. In the Homey app, open `Devices`.
2. Find the `Homey Energy Dongle` device tile and press and hold it.
3. Tap the settings icon in the upper-right corner.
4. Open `Advanced Settings`, find `Local API`, and set it to `Enabled`.
5. Note the dongle IP address from the Homey app.
6. In Home Assistant, open the `Homey P1` integration and enter the dongle IP.

These steps follow Homey’s support article for the Local API:
[Homey Energy Dongle Local API](https://support.homey.app/hc/en-us/articles/18985951863452-Homey-Energy-Dongle-Local-API).

## Configuration

After adding the integration, enter the IP address of your Homey Energy Dongle. 

You can update it later from the integration options.

## Features

- Connects to `ws://<homey-p1-ip>/ws`
- Reconnects automatically if the socket drops
- Parses common DSMR telegram fields
- Creates Home Assistant sensors for energy, power, gas, voltage, current, and a few diagnostic counters

## Current scope

This first version is focused on unencrypted DSMR telegrams.

## Notes

- The Homey Energy Dongle must be reachable from Home Assistant on your local network.
- The Homey Energy Dongle only allows a limited number of WebSocket clients at the same time.
- Disabling the Local API in Homey will disconnect all active Local API connections.
- If your meter requires decryption or uses DLMS framing, this integration will need an additional parser step.
