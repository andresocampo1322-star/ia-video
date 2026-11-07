# Modo de animación mejorada — propuesta 3

Esta propuesta **no reemplaza** Stickman IA. El modo original sigue siendo
el valor predeterminado y los motores de guion, Skia, FFmpeg, Piper y Gemini
no se modifican.

## Cómo activarlo

### Interfaz web original
En el paso **Voz y vídeo**, activa la casilla **Animación mejorada
(experimental)** antes de pulsar **Crear vídeo**.
Si no marcas la casilla, el programa usa el mismo flujo de siempre.

### Línea de comandos
```powershell
python -m stickman --guion examples/ia-en-tu-trabajo.json --animacion-mejorada --salida prueba
```

`--animacion-mejorada` también funciona con `--solo-guion`, para poder
inspeccionar el JSON generado antes de renderizar.

## Reglas (deterministas y auditables)
- Se suavizan los recorridos con `move_to` usando
  `movement_ease: "ease_in_out"`.
- En una escena con un solo personaje móvil y cámara `static`,
  se usa `camera: "follow"`.
- Si el mismo personaje aparece en escenas consecutivas con el **mismo
  fondo**, sin `enter` ni `exit` explícitos, se habilita continuidad
  de posición, orientación, pose y expresión.
- Nunca cambia el texto, el reparto, la duración, la voz ni los accesorios.
- La transformación crea una copia del guion; no altera el original.
- No se infieren `run` ni `sneak` de la narración para evitar equivocaciones.

## Evidencia / límites
Pruebas unitarias de idempotencia, inmutabilidad, compatibilidad CLI, web
y reglas; videos `classic.mp4` / `enhanced.mp4` generados mediante
`tools/preview_auto_enhance.py` y comparados visualmente.

El modo es experimental; mejor criterio visual requiere escenas con personajes
móviles. No entrenamos ningún modelo neuronal ni creamos animación 3D.

## Pendientes prioritarios
- Editor visual de pistas y previsualización directa en la web.
- IK de apoyo y anticipación corporal, para dar mayor peso al movimiento.
- Objetos persistentes entre escenas.
- Escenarios multicapa y control de exposición y contraste.
- Medición de tiempos, tamaño de video y uso de memoria del render.
- Revisión de errores y rutas de salida visibles en Windows.

**Nunca fusionar una mejora sin pruebas de regresión y revisión visual.**
