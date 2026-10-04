-- Ejecutar en Supabase > SQL Editor. Idempotente.

-- Tokens de Garmin por usuario. RLS activado SIN politicas: solo la service role (sync) puede leerlos.
create table if not exists garmin_tokens (
  user_id uuid primary key references auth.users(id) on delete cascade,
  tokens text not null,
  updated_at timestamptz default now()
);
alter table garmin_tokens enable row level security;

-- Metricas diarias de Garmin (hrv, sueno, readiness, body battery, estres, resumen...)
create table if not exists daily_metrics (
  user_id uuid references auth.users(id) on delete cascade,
  day date,
  data jsonb not null,
  primary key (user_id, day)
);

create table if not exists activities (
  user_id uuid references auth.users(id) on delete cascade,
  activity_id bigint,
  start_time timestamptz,
  type text,
  data jsonb not null,
  primary key (user_id, activity_id)
);

-- Una recomendacion por dia: hoy + proximos dias + analisis detallado
create table if not exists recommendations (
  user_id uuid references auth.users(id) on delete cascade,
  day date,
  today jsonb,        -- {titulo, tipo, duracion_min, intensidad, detalle, motivo}
  upcoming jsonb,     -- [{day, titulo, tipo, duracion_min, intensidad}]
  analysis text,      -- overview detallada en texto
  created_at timestamptz default now(),
  primary key (user_id, day)
);

-- Cada usuario solo LEE lo suyo; escribe la service role.
alter table daily_metrics enable row level security;
alter table activities enable row level security;
alter table recommendations enable row level security;
drop policy if exists own_read on daily_metrics;
drop policy if exists own_read on activities;
drop policy if exists own_read on recommendations;
create policy own_read on daily_metrics for select using (auth.uid() = user_id);
create policy own_read on activities for select using (auth.uid() = user_id);
create policy own_read on recommendations for select using (auth.uid() = user_id);
