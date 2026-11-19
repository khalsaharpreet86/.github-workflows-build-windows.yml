# Happy Audios WTG Converter

Windows desktop utility for converting Jieli AC696x .wtg prompt audio to MP3 and MP3 to Jieli .wtg.

## Features
- WTG to MP3 and MP3 to WTG
- Multi-file batch conversion
- Drag and drop (if tkinterdnd2 is packaged)
- Selectable output folder
- Source files are preserved; output files receive a _converted suffix
- Uses the validated Jieli 10-byte G.729 WTG frame mapping
- MP3 audio is resampled to 8 kHz mono before G.729 encoding

## Build on Windows
Requirements:
- Windows 10/11 x64
- Python 3.11 x64
- MSYS2 installed at C:\msys64

Open PowerShell in this folder and run:
    Set-ExecutionPolicy -Scope Process Bypass
    .\build_windows.ps1

The executable will be created at:
    dist\HappyAudios_WTG_Converter.exe

The build script downloads the bcg729 DLL through MSYS2 and FFmpeg from the Windows essentials build. Internet access is required during build.

## Technical notes
- WTG is handled as 10-byte Jieli G.729 frames using the mapping validated in this Deepnote project.
- WTG to MP3: unpack Jieli parameters, decode G.729, encode MP3.
- MP3 to WTG: decode to 8 kHz mono PCM, encode 10 ms G.729 frames, repack into Jieli word layout.
- The frame mapping and round-trip layout are validated in Deepnote. Always test generated prompts on the target AC696x hardware before updating firmware.

## Licensing
The bundled bcg729 implementation is GPL-3.0-or-later. FFmpeg and enabled codecs have separate license terms. Retain all notices and comply with the source/redistribution requirements of the exact binaries used when distributing the application.
