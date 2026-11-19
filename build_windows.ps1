# Build Happy Audios WTG Converter on Windows 10/11 x64.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Bash = "C:\msys64\usr\bin\bash.exe"
if (!(Test-Path $Bash)) { throw "Install MSYS2 from https://www.msys2.org/ and keep the default C:\msys64 location." }
$PythonBits = & py -3.11 -c "import struct; print(struct.calcsize('P') * 8)" 2>$null
if ($LASTEXITCODE -ne 0) { throw "Install Python 3.11 x64 and enable the Python Launcher." }
if ($PythonBits.Trim() -ne "64") { throw "A 64-bit Python 3.11 installation is required." }

Write-Host "Installing G.729 library through MSYS2..." -ForegroundColor Cyan
& $Bash -lc "pacman -Sy --noconfirm && pacman -S --needed --noconfirm mingw-w64-x86_64-bcg729"
if ($LASTEXITCODE -ne 0) { throw "Could not install the bcg729 runtime." }
$MingwBin = "C:\msys64\mingw64\bin"
Copy-Item "$MingwBin\libbcg729.dll" "$Root\libbcg729.dll" -Force

Write-Host "Downloading FFmpeg..." -ForegroundColor Cyan
$Zip = "$Root\ffmpeg-release-essentials.zip"
$Temp = "$Root\_ffmpeg_tmp"
Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $Zip
if (Test-Path $Temp) { Remove-Item $Temp -Recurse -Force }
Expand-Archive $Zip $Temp -Force
$Ffmpeg = Get-ChildItem $Temp -Recurse -Filter ffmpeg.exe | Select-Object -First 1
if (!$Ffmpeg) { throw "ffmpeg.exe was not found in the archive." }
Copy-Item $Ffmpeg.FullName "$Root\ffmpeg.exe" -Force

Write-Host "Installing Python build tools..." -ForegroundColor Cyan
& py -3.11 -m pip install --upgrade pip pyinstaller tkinterdnd2
if ($LASTEXITCODE -ne 0) { throw "Could not install Python build tools." }

$PyArgs = @("--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "HappyAudios_WTG_Converter",
    "--add-binary", "$Root\libbcg729.dll;.",
    "--add-binary", "$Root\ffmpeg.exe;.",
    "--collect-all", "tkinterdnd2",
    "$Root\wtg_converter.py")

# Include common MinGW runtime DLLs when present; these may be needed by libbcg729.dll.
foreach ($Dll in @("libgcc_s_seh-1.dll", "libwinpthread-1.dll", "libstdc++-6.dll")) {
    $DllPath = Join-Path $MingwBin $Dll
    if (Test-Path $DllPath) {
        Copy-Item $DllPath (Join-Path $Root $Dll) -Force
        $PyArgs += @("--add-binary", "$Root\$Dll;.")
    }
}

Write-Host "Building the Windows application..." -ForegroundColor Cyan
& py -3.11 -m PyInstaller @PyArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
$Exe = "$Root\dist\HappyAudios_WTG_Converter.exe"
if (!(Test-Path $Exe)) { throw "Build finished but the expected EXE was not found: $Exe" }
Write-Host ""
Write-Host "SUCCESS: $Exe" -ForegroundColor Green
Write-Host "The EXE is unsigned; Windows SmartScreen may show an unknown-publisher warning."
