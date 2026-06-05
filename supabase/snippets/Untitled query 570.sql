create or replace function get_planets()
returns setof project_documents
language sql
as $$
  select * from project_documents;
$$;

select * from get_planets()