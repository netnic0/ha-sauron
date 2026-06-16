# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0](https://github.com/netnic0/ha-sauron/compare/ha-sauron-v0.1.0...ha-sauron-v0.2.0) (2026-06-16)


### Features

* **coordinator:** compute daily_liters from consecutive index readings ([b2843bd](https://github.com/netnic0/ha-sauron/commit/b2843bdbe13651bf2f792ce9c970336c14420de3))
* **pr1:** align API client with real SAUR field names + complete i18n + tests ([485827e](https://github.com/netnic0/ha-sauron/commit/485827edf061834053363f0430ff7448da0052f3))
* **pr1:** align SAUR API client with real field names, complete i18n, add tests ([168fd36](https://github.com/netnic0/ha-sauron/commit/168fd36e7c461ecbefb24ee4b2c9ea9bdc612502))
* **scaffold:** initial SAURon integration skeleton ([c354e1f](https://github.com/netnic0/ha-sauron/commit/c354e1f1f52218609a63a8cd2e2a6f986f5db143))


### Bug Fixes

* **ci:** sort manifest keys for hassfest + add brand PNG assets for HACS ([1b38c72](https://github.com/netnic0/ha-sauron/commit/1b38c72724d97ac3c2a92061aa9ea7171adc43af))

## [Unreleased]

### Added
- Initial scaffold: `api/` sub-package (client, models, exceptions), coordinator,
  config flow (user + reauth), options flow, sensor platform (7 entities),
  i18n EN/FR, CI (hassfest + HACS validation), release-please automation.
