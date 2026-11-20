-- BioTube : compteur de J'aime partagé entre tous les visiteurs.
-- À coller dans Supabase → SQL Editor → New query, puis cliquer sur Run.

create table if not exists public.likes (
  video_id text primary key,
  count integer not null default 0 check (count >= 0)
);

-- Tout le monde peut lire les compteurs, personne ne peut écrire directement.
alter table public.likes enable row level security;
drop policy if exists "Lecture publique" on public.likes;
create policy "Lecture publique" on public.likes for select using (true);
grant select on public.likes to anon;

-- Seule porte d'écriture : +1 ou -1 sur un identifiant de vidéo YouTube valide.
create or replace function public.like_video(vid text, delta integer)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  if delta not in (-1, 1) or vid !~ '^[A-Za-z0-9_-]{11}$' then
    raise exception 'Requête invalide';
  end if;
  insert into likes (video_id, count) values (vid, greatest(delta, 0))
  on conflict (video_id) do update set count = greatest(likes.count + delta, 0)
  returning count into n;
  return n;
end;
$$;

revoke all on function public.like_video(text, integer) from public;
grant execute on function public.like_video(text, integer) to anon;
