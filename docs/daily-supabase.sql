-- =====================================================================
--  StreetJoin — backend del desafío diario
--  Correr este archivo entero en el SQL editor de un proyecto de Supabase.
--  Después, copiar Project URL y anon key (Settings → API) al objeto BACKEND
--  de web/template.html y rebuildear con `python3 web/build_web.py`.
--
--  La anon key es pública por diseño: viaja en el HTML. Lo que protege los
--  datos es que la tabla tiene RLS activo y NINGUNA política, así que nadie
--  la toca directo — todo entra y sale por las dos funciones de abajo, que
--  corren como dueñas y validan lo que reciben.
-- =====================================================================

create table if not exists public.daily_results (
  day      date        not null,
  player   uuid        not null,          -- id del navegador, no es identidad
  nick     text,
  ms       integer     not null,
  streets  integer     not null,
  created  timestamptz not null default now(),
  primary key (day, player)               -- un resultado por jugador por día
);

create index if not exists daily_results_day_ms on public.daily_results (day, ms);

alter table public.daily_results enable row level security;
-- (sin políticas a propósito: el acceso directo con la anon key queda cerrado)

-- El día del juego corta a medianoche de Santiago (UTC−4 fijo, igual que el
-- cliente: lo que importa es que todos jueguen el mismo puzzle).
create or replace function public.sj_today() returns date
language sql stable as $$
  select ((now() at time zone 'UTC') - interval '4 hours')::date;
$$;

-- ---------------------------------------------------------------------
--  Enviar un resultado. Devuelve {rank, total}.
--  El tiempo no se pisa nunca: el primero que entra es el que vale. El apodo
--  sí se puede cambiar después (el jugador lo escribe al ver el ranking).
-- ---------------------------------------------------------------------
create or replace function public.submit_daily(
  p_day date, p_player uuid, p_nick text, p_ms integer, p_streets integer
) returns json
language plpgsql security definer set search_path = public as $$
declare
  v_nick text; v_ms integer; v_rank integer; v_total integer;
begin
  if p_player is null then raise exception 'falta el jugador'; end if;
  -- hoy o ayer: "ayer" cubre al que terminó justo cuando cambiaba el día
  if p_day is null or p_day > sj_today() or p_day < sj_today() - 1 then
    raise exception 'fecha fuera de rango';
  end if;
  if p_ms is null or p_ms < 3000 or p_ms > 7200000 then
    raise exception 'tiempo fuera de rango';
  end if;
  if p_streets is null or p_streets < 1 or p_streets > 80 then
    raise exception 'calles fuera de rango';
  end if;

  v_nick := left(nullif(btrim(regexp_replace(coalesce(p_nick, ''), '\s+', ' ', 'g')), ''), 16);

  insert into daily_results (day, player, nick, ms, streets)
  values (p_day, p_player, v_nick, p_ms, p_streets)
  on conflict (day, player) do update
    set nick = coalesce(excluded.nick, daily_results.nick);

  select ms into v_ms from daily_results where day = p_day and player = p_player;
  -- el puesto cuenta a los estrictamente más rápidos: los empates comparten lugar
  select count(*) + 1 into v_rank from daily_results where day = p_day and ms < v_ms;
  select count(*)     into v_total from daily_results where day = p_day;

  return json_build_object('rank', v_rank, 'total', v_total);
end $$;

-- ---------------------------------------------------------------------
--  El tablero del día: top 20 + las dos distribuciones + el total.
--  Las distribuciones van como listas crudas (topeadas) y los bins los calcula
--  el cliente con los resultados del día, que es lo que los hace legibles.
-- ---------------------------------------------------------------------
create or replace function public.daily_board(p_day date, p_player uuid default null)
returns json
language sql security definer set search_path = public as $$
  with d as (
    select nick, ms, streets, (player = p_player) as me
      from daily_results where day = p_day
  ),
  t as (select * from d order by ms asc limit 20),
  m as (select ms, streets from d order by ms limit 5000)
  select json_build_object(
    'top', coalesce((select json_agg(json_build_object(
              'nick', nick, 'ms', ms, 'streets', streets, 'me', me
            ) order by ms) from t), '[]'::json),
    'times',   coalesce((select json_agg(ms)      from m), '[]'::json),
    'streets', coalesce((select json_agg(streets) from m), '[]'::json),
    'total',   (select count(*) from d)
  );
$$;

revoke all on function public.submit_daily(date, uuid, text, integer, integer) from public;
revoke all on function public.daily_board(date, uuid) from public;
grant execute on function public.submit_daily(date, uuid, text, integer, integer) to anon, authenticated;
grant execute on function public.daily_board(date, uuid) to anon, authenticated;

-- =====================================================================
--  Lo que esto NO resuelve (a propósito, es un juego chico)
--
--  * Un resultado falso mandado desde la consola entra igual: el servidor no
--    tiene el grafo de calles, así que no puede verificar que el camino
--    declarado exista. Si algún día molesta, lo mínimo razonable es mandar la
--    cadena de calles y validarla contra una copia del grafo en el servidor.
--  * El `player` es un uuid del navegador: limita la recarga, no al que se
--    borra el localStorage o abre una ventana privada.
--  * Los apodos no se moderan.
--
--  Limpieza opcional, si la tabla crece: borrar lo de más de 60 días.
--    delete from public.daily_results where day < current_date - 60;
-- =====================================================================
