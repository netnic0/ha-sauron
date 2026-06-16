# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3](https://github.com/netnic0/ha-sauron/compare/ha-sauron-v0.2.2...ha-sauron-v0.2.3) (2026-06-16)


### Bug Fixes

* **brand:** generate proper PNG assets from SAUR SVG + add icon.svg with water drop ([a6e7e19](https://github.com/netnic0/ha-sauron/commit/a6e7e198d9832b92e326336315311a679484d074))
* **coordinator:** query J-1 for daily/weekly data (SAUR always lags by 1 day) ([969d501](https://github.com/netnic0/ha-sauron/commit/969d501203d6f5efc8cd25105645e04eba72592d))
* **i18n+coordinator:** J-1 query, rename weekly/daily sensors, correct sensor date types ([1c989ce](https://github.com/netnic0/ha-sauron/commit/1c989ce67a2651d8884a76c5c999d753c91f80d8))

## [0.2.2](https://github.com/netnic0/ha-sauron/compare/ha-sauron-v0.2.1...ha-sauron-v0.2.2) (2026-06-16)


### Documentation

* add MIT license, expand README, fix sensor regression ([6e298ce](https://github.com/netnic0/ha-sauron/commit/6e298ce3eaf90af76f38e2156424e30083727aca))
* MIT license + expanded README + sensor date fix ([907d3e0](https://github.com/netnic0/ha-sauron/commit/907d3e01d3a9a595e67ac6a5a358aee53f3a239f))

## [0.2.1](https://github.com/netnic0/ha-sauron/compare/ha-sauron-v0.2.0...ha-sauron-v0.2.1) (2026-06-16)


### Bug Fixes

* **code-quality:** hotfix from post-v0.2.0 review ([d7756fd](https://github.com/netnic0/ha-sauron/commit/d7756fdeddbfc2ea83ceece8d445f6d8f00e5a07))
* **code-quality:** hotfix from post-v0.2.0 review ([034b6fe](https://github.com/netnic0/ha-sauron/commit/034b6feef15aad068a8e5eae4f3c72408840a741))

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
