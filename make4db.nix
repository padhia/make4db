{
  lib,
  buildPythonPackage,
  setuptools,
  sqlparse,
  make4db-api,
  make4db-provider ? null,
  yappt,
  pytest,
}:
buildPythonPackage {
  pname = "make4db";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  dependencies = [ sqlparse make4db-api yappt ] ++ lib.optional (make4db-provider != null) make4db-provider;
  build-system = [ setuptools ];
  nativeCheckInputs = [ pytest ];

  meta = with lib; {
    description = "make like tool for databases";
    maintainers = with maintainers; [ padhia ];
  };
}
