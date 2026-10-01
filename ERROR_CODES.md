# Error codes

Every failure in Vox is classified with a short, stable code.
The code appears in the History window and in dialogs, so you can
look up the cause and possible fix here.

Format: `Exxx` where `xxx` groups the code by area.

| Area | Range |
|------|-------|
| Files and input | `E001`-`E009` |
| External dependencies | `E010`-`E019` |
| Transcription process | `E020`-`E029` |
| Resources | `E030`-`E039` |
| Unknown | `E099` |

## Reference

### Files and input

| Code | Meaning | What to do |
|------|---------|------------|
| `E001` | Source file not found | The file was moved or deleted after being added to the list. Re-add it. |
| `E002` | Could not read media information | The file may be corrupted or use an unusual container. Try re-exporting it. |
| `E003` | Unsupported media format | Convert the file to MP4, MOV, MKV, MP3, WAV, M4A or another supported format. |
| `E004` | Output folder is not writable | Check permissions on the folder where the source file lives. |

### External dependencies

| Code | Meaning | What to do |
|------|---------|------------|
| `E010` | whisper-cli not found | Run `brew install whisper-cpp`. |
| `E011` | ffmpeg not found | Run `brew install ffmpeg`. |
| `E012` | ffprobe not found | Comes with ffmpeg: `brew install ffmpeg`. |
| `E013` | Whisper model not found | Delete `~/whisper-models/` and restart Vox to re-download the model. |

### Transcription process

| Code | Meaning | What to do |
|------|---------|------------|
| `E020` | Whisper failed | Look in `~/Library/Logs/Vox.log` for the exact message. Often caused by a corrupt audio track. |
| `E021` | FFmpeg failed | The audio extraction step failed. Try re-encoding the source file. |
| `E022` | Process timed out | Very long or resource-heavy file. Try a shorter clip first. |
| `E023` | Cancelled by user | You pressed Cancel. Not an error. |

### Resources

| Code | Meaning | What to do |
|------|---------|------------|
| `E030` | Out of memory | Close other apps. For long files, switch to a smaller Whisper model in Settings. |
| `E031` | Out of disk space | Free up space, especially in `~/.whisper_cache/`. |
| `E032` | System resources exhausted | Close other apps and try again. |

### Unknown

| Code | Meaning | What to do |
|------|---------|------------|
| `E099` | Unknown error | Check `~/Library/Logs/Vox.log` for the raw message. |
