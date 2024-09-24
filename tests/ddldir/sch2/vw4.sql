create or replace view sch2.vw4 as
select *
from sch2.tb3
join sch1.vw3 using (c1);
