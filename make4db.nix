{
  lib,
  buildPythonPackage,
  setuptools,

  make4db-api,
  sqlparse,
  yappt,

  pytest,

  make4db-duckdb,
  make4db-postgres,
  make4db-snowflake,
}:
buildPythonPackage {
  pname = "make4db";
  version = "0.1.2";
  pyproject = true;
  src = ./.;

  dependencies = [
    sqlparse
    make4db-api
    yappt
  ];
  build-system = [ setuptools ];
  nativeCheckInputs = [ pytest ];

  optional-dependencies = {
    duckdb = [ make4db-duckdb ];
    postgres = [ make4db-postgres ];
    snowflake = [ make4db-snowflake ];
  };

  meta = with lib; {
    description = "make like tool for databases";
    maintainers = with maintainers; [ padhia ];
  };
}
