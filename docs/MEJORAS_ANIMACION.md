# Animaciones: ampliación incremental 01

## Regla principal
El motor original **no se sustituye**. La rama `main` queda intacta hasta
que esta ampliación pase pruebas y se apruebe visualmente en MP4.

## Lo añadido
Por personaje y por escena se acepta el campo opcional `gait`:
- `walk`: modo predeterminado. Conserva las velocidades, poses y
  oscilación vertical del proyecto original.
- `run`: más desplazamiento por segundo y ciclo con mayor zancada y braceo.
- `sneak`: desplazamiento lento, flexión de rodillas y menor rebote.

Ejemplo parcial de un personaje en una escena:

```json
{
  "id": "protagonista",
  "x": -0.7,
  "gait": "run",
  "actions": [
    {"at": 0.0, "move_to": 0.7}
  ]
}
```

No se modifica el significado de `pose`, `move_to`, `camera`,
`speaker`, `background` ni ninguna otra propiedad.

## Condiciones de aceptación
1. Los ejemplos originales renderizan sin cambios visuales.
2. Con `gait` omitido, el ciclo de andar conserva valores y duración.
3. Con `run` y `sneak`, los movimientos se ven diferenciados y fluidos.
4. No hay regresiones en las pruebas existentes de esquema, render y tween.
5. Comparación manual de un MP4 original y uno experimental antes del merge.

## Limitaciones
Este cambio **no** añade escenarios 3D, modelos generativos ni video realista.
La fluidez y el contacto de pies deben evaluarse visualmente en Windows.

## Validación automática
La comprobación obligatoria en la PR ejecuta las pruebas unitarias y de render
**exceptuando** `test_piper_captions_follow_asr_words`, una integración
original Piper/Whisper dependiente de descargas, versiones y resultados ASR.
La prueba original no se modifica y puede ejecutarse de forma independiente.
Su exclusión de CI **no** equivale a dar por aprobada la alineación de voz.

## Videos comparativos
El flujo de GitHub Actions produce los MP4 `walk.mp4`, `run.mp4` y
`sneak.mp4` con el **mismo renderizador del proyecto** y un audio de prueba
silencioso; no son animatics alternativos. Se obtienen desde la ejecución
exitosa en Actions, artefacto `comparacion-animaciones-01`.
La inspección visual humana sigue siendo obligatoria antes de fusionar.
