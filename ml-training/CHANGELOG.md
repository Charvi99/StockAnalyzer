# Changelog

All notable changes to ML-Training project will be documented in this file.

## [3.0.0] - 2026-02-12

### Added
- YAML configuration system with environment variable support
- Configuration profiles (default, binary_classification, multiclass)
- Architecture documentation
- Configuration reference documentation
- Archive directory for obsolete code and data

### Changed
- Streamlined README.md (220 → 85 lines, 61% reduction)
- Removed all TCN model references
- Updated all scripts to use unified config system
- Improved code organization and structure

### Removed
- Duplicate scripts_host directory (archived)
- 24+ obsolete scripts (archived)
- Old test datasets (archived, keeping latest 5)
- Old models (archived, keeping latest 3)

### Fixed
- Configuration inconsistencies across scripts
- Scattered hard-coded parameters
- Documentation redundancy
- Config.py environment variable parsing bug (key[13:] → key[12:])

### Performance
- Disk space recovered: 3-7 GB from archiving old data
- No performance impact to core ML functionality

## [2.x] - Previous Versions

See git history for changes prior to v3.0.0
