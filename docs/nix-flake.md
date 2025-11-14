Running Makhfuuz with Nix (flake)
=================================

This repository now provides a `flake.nix` so you can run the desktop app with `nix run`.

Quick run (build and run in-place):

```bash
nix run .#makhfuuz
```

Install to your user profile (via nix profile):

```bash
nix profile install .#makhfuuz
# then run with
makhfuuz
```

Add to a NixOS system configuration
-----------------------------------

You can add this flake as an input to your system flake and include the package in `environment.systemPackages` so it becomes available as a desktop application for all users.

Example `flake.nix` snippet for your system configuration:

```nix
{ inputs, ... }:

let
  # add the local or remote flake
  makhfuuz = inputs.makhfuuz;
in
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
    makhfuuz.url = "github:orhnk/Makhfuuz"; # or path: "." for local
  };

  outputs = { self, nixpkgs, makhfuuz, ... }:
  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
  in
  {
    nixosConfigurations = {
      my-host = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [
          ({ config, pkgs, ... }: {
            environment.systemPackages = with pkgs; [ makhfuuz.packages.${system}.makhfuuz ];
          })
        ];
      };
    };
  }
```

Notes
-----
- The flake uses `build.nix` as the package derivation. `build.nix` already creates a wrapped executable at `$out/bin/kohighlights` and installs desktop files and an icon when present.
- If you want the app to integrate with desktop launchers, ensure an icon file exists at the repository root named `icon.png` or adjust `build.nix`.
- The flake currently pins `nixpkgs` to `nixos-23.11`; change the input in `flake.nix` to your desired channel or commit to match your system.
