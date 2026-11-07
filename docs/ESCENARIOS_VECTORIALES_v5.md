# Escenarios y atmósfera 2D (propuesta 5)

El motor original se conserva. Esta mejora **no activa** escenarios de
forma automática ni sustituye el renderizador. El estilo sigue siendo
vectorial 2D, con personajes y voces originales.

## Opciones nuevas, desactivadas por defecto

Por escena:
- `environment: "none"` (original), `"street"` (calle), `"room"`
  (habitación), `"supermarket"` (supermercado) o `"forest"` (bosque).
- `atmosphere: "none"` (original), `"rain"`, `"snow"` o `"fog"`.

Los fondos están dibujados por debajo de los personajes con Skia; la lluvia,
nieve y niebla se dibujan en primer plano antes de los subtítulos.
El tratamiento de cámara existente afecta al escenario de modo coherente.

Ejemplo:
```json
{
  "narration": "Nora entra al supermercado durante una tormenta.",
  "background": "noche",
  "environment": "supermarket",
  "atmosphere": "rain",
  "camera": "pan_right",
  "characters": [{"id": "nora", "x": -0.4, "pose": "guard"}]
}
```

## Compatibilidad y protección de continuidad
Los guiones existentes sin campos nuevos se renderizan con los colores y
movimientos originales. El modo mejorado automático no hereda posiciones
entre entornos diferentes aun cuando el color de fondo sea idéntico.

## Pruebas y evidencia
- Equivalencia de capturas antiguas y captura con opciones `none` explícitas.
- Pruebas de escenarios y clima en 16:9 y 9:16.
- Animación de lluvia determinista por instante.
- `python -m tools.preview_scenery` genera `original.mp4` y
  `escenarios_lluvia.mp4` con el mismo guion.

## Próximos retos
Mejorar geometría de los fondos, objetos persistentes, profundidad con
paralaje, sombras por luz, oclusión y contactos de pies; estas funciones
NO se consideran implementadas en esta propuesta.
