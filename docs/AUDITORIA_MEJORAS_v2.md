# Auditoría incremental del motor de animación — revisión 2

## Garantía fundamental: no sustituir el motor
La referencia inmutable es `main` de `ia-video`, copia del motor público
`iaquetrabaja/stickman-ia`. Todo cambio se desarrolla y compara en otra rama.
La mejora 2 se construye sobre la propuesta 1 (locomoción `walk/run/sneak`).

### Componentes revisados (fuente original)
| Componente | Capacidades conservadas | Mejoras posibles |
|---|---|---|
| `schema.py` | Guion saneado/validado; reparto; tiempos relativos; cámaras | Ampliar opciones sin romper JSON legado |
| `render.py` | Skia, tiempo por escena, cámara, voz/gestos, subtítulos, MP4 FFmpeg | Continuidad, movimientos con easing, seguimiento, transiciones |
| `rig/skeleton.py` | Cinemática, longitudes invariables, suelo | Plantado del pie con IK sin deformaciones |
| `rig/poses.py` | Poses originales y caminar | Expandir expresiones corporales con ciclos opcionales |
| `rig/draw.py` | Personajes vectoriales, cabello, accesorios, sombras | Profundidad por capas, microgestos y mejora de silueta |
| `audio.py`, `align.py`, `tts.py` | Voz y subtítulos | Pruebas robustas sin alterar sincronización |
| `pipeline.py`, `cli.py`, `web/` | Generación, exportación, interfaz | Progreso, errores claros, vistas previas sin sustituir render |

## Mejoras implementadas en esta rama (opcionales)
- `movement_ease="ease_in_out"`: la posición acelera y frena con smoothstep;
  `"linear"` conserva la interpolación del autor (valor predeterminado).
- `continue_from_previous=true`: para personaje presente en escenas
  consecutivas, mantiene su posición y orientación de salida, y mezcla
  pose y emoción hacia el estado solicitado en el siguiente plano.
  Se ignora si el personaje tiene `enter="left"`, `enter="right"` o `enter="pop"`
  para evitar alterar entradas explícitas.
- `camera="follow"`: la cámara acompaña al personaje hablante o al primero
  de la escena. Las cámaras y keyframes originales siguen intactos.
- `transition="fade_from_black"`: fundido de entrada de 0,35 s; `"cut"` es
  el comportamiento predeterminado.

Ejemplo (fragmento de una escena de guion válido):
```json
{
  "narration": "Nora avanza mientras la cámara la acompaña.",
  "camera": "follow",
  "transition": "fade_from_black",
  "characters": [
    {
      "id": "nora",
      "x": -0.6,
      "gait": "run",
      "movement_ease": "ease_in_out",
      "continue_from_previous": true,
      "actions": [{"at": 0.1, "move_to": 0.6}]
    }
  ]
}
```

## Pruebas de aceptación
1. Ningún JSON original debe necesitar cambios.
2. Sin opciones explícitas, posiciones, gestos, cámara y salida son los mismos.
3. Con las opciones nuevas, la animación sigue saliendo de `VideoRenderer`.
4. El nuevo plano conserva posición/orientación si el personaje sigue en escena.
5. Se produce `legacy.mp4` y `mejoras_optin.mp4`, más PNG por fotogramas.
6. El merge a `main` requiere inspección visual, no solo `pytest`.

## Mejoras recomendadas para etapas posteriores (no implementadas aquí)
**P1 — Mayor impacto visual:**
- Plantado de pies mediante IK y compensación de suelo durante caminata y carrera.
- Transición de velocidad y fase de zancada al cambiar de `walk` a `run`.
- Acciones corporales expresivas (agacharse, girar, tropezar, empujar, recoger).
- Detección y mitigación de superposición de personajes/props.

**P2 — Lenguaje cinematográfico y continuidad:**
- Encuadres automáticos que respeten grupos y espacio negativo del subtítulo.
- Transiciones más elaboradas con controles de duración y exposición.
- Ambiente vectorial por capas, profundidad/paralaje e iluminación 2D.
- Persistencia temporal de objetos entre escenas con identidad explícita.

**P3 — Producción, interfaz y rendimiento:**
- Previsualización interactiva de guiones antes del render final.
- Porcentaje y registro de errores visibles; botón para abrir archivo exportado.
- Metadatos de calidad, perfil de FPS y validación FFmpeg.
- Caché y presupuestos de memoria CPU/GPU para equipos modestos.
- Reglas de consistencia visual por episodio; informes de regresión MP4.

## Límites reconocidos
Esta ampliación NO crea modelos generativos ni cambia a 3D, NO incorpora
movimiento neuronal y NO modifica Piper, Skia, FFmpeg ni las caras originales.
El seguimiento de cámara funciona sobre un escenario 2D; para impacto
cinematográfico mayor hará falta mejorar también los fondos y los objetos.
