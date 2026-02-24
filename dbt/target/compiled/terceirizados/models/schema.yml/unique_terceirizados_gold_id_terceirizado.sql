
    
    

select
    id_terceirizado as unique_field,
    count(*) as n_records

from "terceirizados-gold"."main"."terceirizados_gold"
where id_terceirizado is not null
group by id_terceirizado
having count(*) > 1


