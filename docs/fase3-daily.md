# StreetJoin — Fase 3: Desafío diario y ranking (2026-08-27)

El mismo puzzle para todos, una vez por día, con **ranking del día** y **dos
distribuciones**. Se entra por la tarjeta 📅 del menú principal.

Cambio respecto de lo planificado: el plan decía *dos leaderboards sin nombres*
(solo distribuciones). Se agregó arriba un **top 20 con apodo**, porque competir
contra la población y competir contra personas no son la misma cosa: la
distribución te ubica, el ranking te da a quién alcanzar. Quedaron los dos.

## Cómo funciona

| | |
|---|---|
| Puzzle | `newPuzzlePlaces(daySeed(fecha))` — lugares a ciegas, el modo principal |
| El día | Corta a medianoche de Santiago, con **UTC−4 fijo** (sin horario de verano) |
| Se juega | Una sola vez. El cronómetro arranca con la primera calle, como siempre |
| Ranking | Por **tiempo**; las calles usadas se muestran pero no ordenan |
| Puesto | Cantidad de gente estrictamente más rápida + 1 (los empates comparten lugar) |

**La semilla es un hash FNV de la fecha**, no el número de día. Con `mulberry`,
semillas correlativas dan primeras salidas parecidas, y dos días seguidos tienen
que ser puzzles sin ningún parentesco.

**Una sola partida por día, en serio.** El estado se guarda en `localStorage` al
*primer intento*, no al terminar: recargar la página no cambia el puzzle, no
reinicia el reloj y no da un segundo intento. Si volvés a mitad de partida el
cronómetro sigue corriendo desde el primer intento real (`t0` se reconstruye con
la hora de pared), y se avisa en el panel. Con el diario ya jugado, la tarjeta
del menú lleva al ranking, no a una partida nueva.

En el diario no existen ↻ ni 📍: no hay nada que elegir ni puzzle que volver a
tirar. Y el resultado del diario **no toca tu mejor marca** de lugares a ciegas:
son dos cosas distintas.

## Las dos distribuciones

Son de frecuencia y sin nombres — sirven para ubicarte en la población, que es
lo que el puesto solo no dice cuando hay mucha gente.

- **Tiempos**: bins **autocalculados con los resultados del día**, no fijos. El
  ancho sale de una lista de valores redondos (10 s, 15 s, 30 s, 1 min, 90 s…),
  el primero que deje ~9 bins cubriendo el rango. Así la distribución se lee bien
  tenga la forma que tenga.
- **Calles usadas**: un bin por valor discreto, topeado a 15 valores.

Tu barra va marcada, y debajo va el percentil ("más rápido que el 54 % de los que
jugaron hoy"). En la de tiempos, **tu barra se rotula con tu tiempo real** y no
con el borde del bin: ver `3:00` resaltado cuando hiciste 4:07 se lee como un
error, y como tu tiempo cae dentro del bin el eje sigue en orden igual.

## El apodo

Se pide **después** de jugar, en la pantalla del ranking, no antes: pedir un
nombre para entrar es una barrera y el juego se puede jugar sin eso. Sin apodo el
resultado igual cuenta en las distribuciones y aparece como *anónimo*. Cambiarlo
reenvía el resultado y actualiza la fila; el tiempo no se puede pisar nunca.

## Backend

Supabase, hablado directo por `fetch` contra PostgREST — sin `supabase-js`, para
no romper el "un archivo autocontenido". Toda la red vive detrás de dos
funciones, `net.submitResult()` y `net.fetchBoard()`.

**Sin credenciales configuradas el juego funciona igual**, contra una población
simulada determinista a partir de la fecha. No es un adorno: es lo que permite
tener la pantalla entera armada y testeada antes de que exista el servidor, y lo
que hace que un fallo de red no rompa el juego.

Para enchufarlo:

1. Correr `docs/daily-supabase.sql` entero en el SQL editor del proyecto.
2. Copiar la URL y la clave **publicable** (Settings → Data API / API Keys) al
   objeto `BACKEND` de `web/template.html`.
3. `node web/test_daily_live.mjs` para verificar contra el Supabase real.
4. `python3 web/build_web.py`, commit y push.

**Las claves nuevas no son JWT.** Supabase reemplazó `anon` por claves
publicables opacas (`sb_publishable_…`), y esas **no se pueden mandar en
`Authorization: Bearer`** — el gateway rechaza el pedido. `rpc()` distingue por
la forma de la clave (`^eyJ` = JWT viejo) y manda el header solo cuando
corresponde, así funcionan las dos. `apiBase()` acepta tanto el *Project URL*
como el endpoint REST completo, que es lo que uno termina copiando del
dashboard.

**El plan gratis pausa el proyecto tras una semana sin actividad.** Con gente
jugando no pasa; si el juego queda quieto, hay que restaurarlo desde el
dashboard.

El esquema es una tabla con RLS activo y **ninguna política** — nadie la toca
directo con la anon key. Todo pasa por dos funciones `security definer`:
`submit_daily` (valida rango de fecha, tiempo y calles; una fila por jugador y
día; el tiempo no se pisa, el apodo sí) y `daily_board` (top 20 + las dos listas
para los histogramas + el total).

**Lo que no resuelve, a propósito:** el servidor no tiene el grafo de calles, así
que no puede verificar que el camino declarado exista — un resultado falso desde
la consola entra igual. Para un juego chico es aceptable; si molesta, lo mínimo
razonable es mandar la cadena de calles y validarla contra una copia del grafo.

## Compartir

Texto plano al portapapeles, estilo Wordle, sin spoilers del puzzle:

```
StreetJoin 📅 #27
⏱ 4:07 · 6 calles
🏅 puesto 97 de 211
https://juanisenin.github.io/streetjoin/
```

## Testing

`web/test_daily.mjs`, 32 verificaciones en verde, con contextos de navegador
separados para simular jugadores distintos:

- el puzzle sale de la semilla del día y **dos sesiones distintas del mismo día
  reciben el mismo puzzle**; días consecutivos, semillas sin parentesco;
- el resultado se guarda, se envía y el puesto coincide con cuántos fueron más
  rápidos en la distribución;
- top 20 ordenado, dos histogramas con bins razonables, tu bin marcado en ambos,
  percentiles presentes, texto de compartir bien formado;
- el apodo se normaliza (`"  el  cuico  "` → `"el cuico"`) y aparece en tu fila;
- **recargar a mitad de partida** no cambia el puzzle ni reinicia el reloj;
- con el diario jugado, la tarjeta del menú lleva al ranking;
- la capa de red devuelve la forma esperada y la población simulada es
  determinista entre llamadas.

Las verificaciones del navegador **apagan el backend** (`daily.backend`) y
corren contra la población simulada: son reproducibles y no ensucian el ranking
real con partidas de test.

`web/test_daily_live.mjs` es el otro lado: sin navegador, contra el Supabase de
verdad. Comprueba que las funciones existen y son ejecutables por `anon`, que el
día del servidor coincide con el del cliente, que **la tabla no se toca directo**
con la clave pública, que el puesto sale bien con dos jugadores, que el tiempo no
se pisa pero el apodo sí se puede cambiar, la forma del tablero, y las cuatro
validaciones del servidor (tiempo absurdo, calles absurdas, fecha vieja, fecha
futura). Escribe con la fecha de **ayer** y uuids al azar, así el ranking que ve
la gente queda intacto.

`web/test_blind.mjs` completo sigue en verde, incluidas las 40 partidas del
camino final y las 60 del desvío de ruta.
