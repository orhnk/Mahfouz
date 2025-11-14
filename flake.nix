{
  description = "Makhfuuz (KoHighlights) - flake packaging to run with `nix run`";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
  };

  outputs = { self, nixpkgs, ... }:
  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    appPkg = pkgs.callPackage ./build.nix {};
  in
  {
    packages.${system} = {
      makhfuuz = appPkg;
      default = appPkg;
    };

    apps.${system}.makhfuuz = {
      type = "app";
      program = "${appPkg}/bin/kohighlights";
      # optional desktop metadata to help some tools discover the app
      desktop = {
        Name = "KoHighlights";
        Exec = "${appPkg}/bin/kohighlights";
        Icon = "${appPkg}/share/icons/hicolor/48x48/apps/kohighlights.png";
        Type = "Application";
        Categories = "Utility";
      };
    };

    defaultPackage.${system} = appPkg;
    defaultApp.${system} = self.apps.${system}.makhfuuz;
  };
}
