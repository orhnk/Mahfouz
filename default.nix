{ pkgs ? import <nixpkgs> {}, ... }:

# Legacy default.nix entrypoint. The real build is defined in build.nix and
# `flake.nix` provides a modern flake-based interface. This file keeps
# compatibility with tools that expect a `default.nix`.

let
  build = pkgs.callPackage ./build.nix {};
in
{ inherit build; }
