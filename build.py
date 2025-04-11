#!/usr/bin/env python3
import os
import platform
import subprocess
import sys
from pathlib import Path

def run_command(cmd):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def build_wheel():
    print("Building wheel...")
    run_command([sys.executable, "-m", "build", "--wheel"])

def build_sdist():
    print("Building source distribution...")
    run_command([sys.executable, "-m", "build", "--sdist"])

def build_appimage():
    if platform.system() != "Linux":
        print("AppImage can only be built on Linux")
        return
    
    print("Building AppImage...")
    # Install required tools
    run_command(["pip", "install", "pyinstaller"])
    
    # Create spec file
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['sshm.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='sshm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
    with open("sshm.spec", "w") as f:
        f.write(spec_content)
    
    # Build with PyInstaller
    run_command(["pyinstaller", "sshm.spec"])
    
    # Create AppImage
    run_command(["wget", "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"])
    run_command(["chmod", "+x", "appimagetool-x86_64.AppImage"])
    
    # Create AppDir structure
    os.makedirs("AppDir/usr/bin", exist_ok=True)
    os.makedirs("AppDir/usr/share/applications", exist_ok=True)
    
    # Copy binary
    run_command(["cp", "-r", "dist/sshm/*", "AppDir/usr/bin/"])
    
    # Create desktop file
    desktop_content = """
[Desktop Entry]
Name=SSHM
Comment=SSH TUI Manager
Exec=sshm
Icon=sshm
Type=Application
Categories=Utility;
"""
    with open("AppDir/usr/share/applications/sshm.desktop", "w") as f:
        f.write(desktop_content)
    
    # Build AppImage
    run_command(["./appimagetool-x86_64.AppImage", "AppDir"])

def build_nix():
    if platform.system() != "Linux":
        print("Nix package can only be built on Linux")
        return
    
    print("Building Nix package...")
    # Create default.nix
    nix_content = """
{ stdenv, python3Packages }:

python3Packages.buildPythonApplication {
  pname = "sshm";
  version = "0.1.0";
  src = ./.;
  propagatedBuildInputs = with python3Packages; [
    textual
    cryptography
    paramiko
  ];
  doCheck = false;
}
"""
    with open("default.nix", "w") as f:
        f.write(nix_content)
    
    # Build with nix-build
    run_command(["nix-build"])

def main():
    # Create dist directory if it doesn't exist
    os.makedirs("dist", exist_ok=True)
    
    # Build wheel and sdist
    build_wheel()
    build_sdist()
    
    # Build platform-specific packages
    if platform.system() == "Linux":
        build_appimage()
        build_nix()
    
    print("\nBuild complete! Check the dist/ directory for your packages.")

if __name__ == "__main__":
    main() 