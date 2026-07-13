# Dev/test environment. `nix-shell --run "PYTHONPATH=. pytest tests -q"`
{ pkgs ? import <nixpkgs> {} }:
let
  btDynamic = pkgs.python3Packages.buildPythonPackage rec {
    pname = "bt_dynamic";
    version = "0.1.3";
    pyproject = true;
    src = pkgs.python3Packages.fetchPypi {
      inherit pname version;
      hash = "sha256-NVuvUkr0BpedpaYIjXdeOQH62EeQewX2+AWk9XE5d0M=";
    };
    build-system = [ pkgs.python3Packages.hatchling ];
    dependencies = with pkgs.python3Packages; [ pandas numpy ];
  };
in
pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages (ps: with ps; [ pandas numpy pytest btDynamic ]))
  ];
}
