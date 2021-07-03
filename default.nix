{ pkgs ? import <nixpkgs> {} }:
with pkgs;
let 
  my_program = with python38Packages; buildPythonApplication {
    pname = "my_server";
    version = "0.0.1";
    propagatedBuildInputs = [ uvicorn starlette ];
    src = ./.;
  };
in {
  software = my_program;

  image = dockerTools.buildImage {
    name = "my_server";
    tag = "latest";
    created = "now";
    contents = [ my_program ];
    config.Cmd = [ "${my_program}/bin/server.py" ];
  };
}
