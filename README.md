# MathGame1

Juego multijugador para móviles. Una persona crea la partida y comparte el código;
los demás se unen con su propio nombre. El creador inicia la partida cuando todos
están presentes. Se necesitan al menos dos jugadores.

## Ejecutar

Con Python 3.10 o posterior, instala las dependencias con
`pip install -r requirements.txt` y ejecuta
`python MathGame1.py`. Abre la dirección mostrada por el servidor, o
`http://localhost:8080` en el mismo ordenador.

Para desplegarlo en Render, crea un **Web Service** con este repositorio,
entorno Python, comando de instalación `pip install -r requirements.txt` y
comando de inicio `python MathGame1.py`. La aplicación escucha en `0.0.0.0`
y utiliza el puerto indicado por la variable `PORT`.

Las partidas se guardan exclusivamente en la memoria del proceso: se pierden
cuando el servicio se reinicia o se vuelve a desplegar. Utiliza una sola
instancia y un solo proceso; las partidas no se comparten entre instancias.
Render puede suspender los servicios inactivos según el plan contratado.
El código permite unirse antes de empezar. La dirección personal de la página
identifica al jugador: no la compartas; comparte solo el código.

## Reglas aplicadas

- Todos juegan una vez por turno; el siguiente comienza cuando todos han
  actuado. Un jugador que ya haya completado su tablero espera, pero puede
  seguir colocando calaveras en tableros ajenos.
- La llave obliga a usar una puerta y prevalece sobre el corazón. El corazón
  permite escoger del 1 al 15 si no hay llave. La calavera prevalece sobre
  ambos y asigna aleatoriamente a cada jugador el tablero de otra persona,
  sin mostrar su identidad. Si el tablero asignado no tiene casillas normales
  libres, ese jugador pasa.
- Si una tirada normal o con llave impediría jugar a algún jugador que no
  haya terminado, se repite para todos. También se repite una tirada de
  calavera si ya no quedan casillas normales libres en ningún tablero.
- Cada casilla numérica que tenga al menos un número consecutivo adyacente
  aporta un punto, independientemente de cuántas secuencias la incluyan.
  La adyacencia incluye horizontal, vertical y diagonal.
- Cada valor con al menos un grupo conectado de tres o más casillas iguales
  aporta tres puntos, una sola vez por valor. Cada calavera aporta dos puntos
  si tiene un 9 adyacente, y resta dos en caso contrario. Los empates se
  anuncian como tales.

Para ejecutar las pruebas: `python -m unittest test_MathGame1`.
