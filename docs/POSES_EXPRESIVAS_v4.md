# Repertorio de poses expresivas — propuesta 4

## Regla de compatibilidad
Se mantienen **sin cambios** todas las poses originales, la cinemática,
el interpolador, las caras, la voz y la forma de exportar video.

## Seis poses adicionales (opt-in)
- `crouch`: agacharse y flexionar rodillas.
- `cower`: protegerse ante un peligro.
- `stagger`: tambalearse.
- `attack`: embestir o atacar.
- `reach`: alcanzar un objeto a distancia.
- `guard`: cubrirse en posición defensiva.

Se usan exactamente en los campos `pose` y `actions[].pose` originales,
por ejemplo:

```json
{
  "id": "nora",
  "x": -0.2,
  "pose": "idle",
  "actions": [
    {"at": 0.2, "pose": "guard"},
    {"at": 0.65, "pose": "cower"}
  ]
}
```

Estas poses utilizan `Track`, `forward`, `ground_offset` y la estructura
original, sin esqueleto nuevo ni animatics alternativos.

## Verificación
Las pruebas comprueban el registro, la inmutabilidad de las poses anteriores,
longitudes fijas de los huesos, los alias de guion, interpolación continua
y fotogramas Skia de cada pose.

`python -m tools.preview_expressive_poses` genera un MP4 de 12 segundos
con las seis poses; un conjunto de PNG facilita revisar el resultado.

## Criterio de aceptación
No fusionar a `main` hasta que el MP4 demuestre siluetas claras y poses
que se distingan de `idle`. Si una pose queda artificial, ajustarla
únicamente a ella o descartarla, sin afectar el resto.
