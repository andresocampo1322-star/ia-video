# La vecina — episodio piloto para probar el motor original

Pulsa **Cargar historia zombi** en Studio Pro, elige **Motor original
Stickman IA 2D**, y después **Generar episodio MP4**. No necesitas
ComfyUI ni claves de servicios externos. Sí necesitas las dependencias
originales del proyecto (Python 3.12, skia-python, Piper y FFmpeg).
La primera síntesis Piper puede descargar su voz española.

Salida: `episodio_stickman.mp4`, además de JSON y SRT.

**Limitación importante:** el motor original dibuja personajes y escenarios
vectoriales. La televisión, la nevera, el sangrado de nariz, la cerca y las
volteretas complejas de la vecina se mencionan en el libreto, pero
**todavía no tienen una recreación física de detalle**. Verás interpretación
aproximada mediante poses y movimientos. Esta prueba establece una referencia
real para seguir mejorando el repositorio, no iguala el anime de la muestra.

Para reproducir la escena en la ruta generativa avanzada necesitarás un
modelo de imagen/video instalado, además de referencias de personaje.
