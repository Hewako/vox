# Changelog

All notable changes to Vox are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-01

### Added
- Auto-update from GitHub Releases: the app checks for a new version on launch and can install it in one click.
- History window: every transcription is saved with its result. Open, retry, or delete any entry from the list.
- Settings window: all options moved into a separate modal window with Apply and Cancel.
- Changelog window: browse the full version history from the About dialog.
- Error codes E001-E099: failures are now classified for easier debugging.
- Log rotation: Vox.log rotates at 1 MB, keeping 5 backups.

### Changed
- Main window is cleaner: options moved to the settings window.
- History list rewritten on Canvas for reliable status icon rendering on macOS.
- Status icons in the history are tinted green (success) and red (error).

### Fixed
- Fixed get_icon_base64 import in the splash window.
- Fixed settings not being saved on close.
- Removed deprecated theme key from older settings files.

## [1.0.0] - 2026-09-29

### Added
- Initial release.
- Local audio and video transcription using whisper.cpp.
- Support for 99 languages with automatic detection.
- VAD to remove silence and reduce hallucinations.
- SRT subtitle output.
- Batch processing of up to 4 files in parallel.
- Cache for repeat transcriptions.
- Drag and drop support.
- 12 interface languages.
- First-run wizard for downloading Whisper models.
