create or replace view {{ this }} as
select *
from {{ ref("sch2.tb3") }}
join {{ ref("sch1.vw3") }} using (c1);
