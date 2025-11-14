{
  stdenv,
  lib,
  python3,
  qt6,
  makeWrapper,
  copyDesktopItems,
  makeDesktopItem,
  fetchFromGitHub, # Only needed if fetching from source control
}: let
  appSrc = ./src;

  # appSrc = fetchFromGitHub {
  #   owner = "your_username";
  #   repo = "your_repo";
  #   rev = "commit_hash_or_tag";
  #   hash = "sha256-...";
  # };

  pythonEnv = python3.withPackages (ps: [
    ps.pyside6
    ps.beautifulsoup4
    ps.requests
    ps.packaging
  ]);
in
  stdenv.mkDerivation rec {
    pname = "kohighlights";
    version = "0.1.0";

    src = appSrc;

    nativeBuildInputs = [
      qt6.wrapQtAppsHook
      makeWrapper
      copyDesktopItems
    ];

  buildInputs = [ pythonEnv qt6.qtbase ];

    # Port the app to PySide6/Qt6 at build time
    postPatch = ''
      # switch runtime to Qt6
      substituteInPlace boot_config.py \
        --replace "USE_QT6 = False" "USE_QT6 = True"

      # update all PySide imports to PySide6
      find . -type f -name '*.py' -print0 | xargs -0 sed -i 's/from PySide2/from PySide6/g'
      find . -type f -name '*.py' -print0 | xargs -0 sed -i 's/import PySide2/import PySide6/g'
    '';

    desktopItems = [
      (makeDesktopItem {
        name = "kohighlights";
        desktopName = "KoHighlights";
        exec = "kohighlights";
        icon = "kohighlights"; # Ensure you have an icon file
        categories = ["Utility"];
        comment = "Sijjil Al-Maktab";
        terminal = false;
      })
    ];

    installPhase = ''
      runHook preInstall

      # Install application files
      mkdir -p $out/share/kohighlights
      cp -r ./* $out/share/kohighlights/

      # Install executable wrapper
      mkdir -p $out/bin
      makeWrapper ${pythonEnv}/bin/python $out/bin/kohighlights \
        --add-flags "$out/share/kohighlights/main.py" \
        --set QT_DEBUG_PLUGINS "1" \
        --prefix PYTHONPATH : "$out/share/kohighlights" \
  --prefix QT_PLUGIN_PATH : "${qt6.qtbase}/${qt6.qtbase.qtPluginPrefix}"

      # Install icon (replace with your actual icon file)
      if [ -f ./icon.png ]; then
        mkdir -p $out/share/icons/hicolor/48x48/apps
        cp ./icon.png $out/share/icons/hicolor/48x48/apps/kohighlights.png
      fi

      runHook postInstall
    '';
  }
