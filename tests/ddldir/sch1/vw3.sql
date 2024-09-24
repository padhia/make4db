create or replace view sch1.vw3 as
select *
from sch1.tb1
join sch1.tb2 using (c1);
