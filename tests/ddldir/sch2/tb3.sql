create or replace table {{ this }} (
   obj_database varchar(255) not null default '{{ env_var.DBNAME }}',
   obj_schema   varchar(255) not null default '{{ this.sch }}',
   obj_name     varchar(255) not null default '{{ this.name }}',
   c4           varchar(20)
);
