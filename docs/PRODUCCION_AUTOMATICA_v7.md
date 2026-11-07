# ia-video | Producción automática experimental v7

## Objetivo real

Conectar en **una sola ejecución**:
**libreto → interpretación → biblia de personajes → imagen maestra
→ imagen por plano → video por plano → comprobación técnica → MP4**.

Esta función es opcional. El programa Stickman IA original no se modifica.

## Lo implementado y lo que no

Implementado en la PR: orquestador de stages, imagen maestra persistente por
personaje, inyección de 1-4 referencias por plano en el workflow compatible,
imagen inicial para modelos imagen-a-video, subida a ComfyUI local, espera y
descarga de trabajos, comprobación básica de duración/formato y movimiento,
montaje FFmpeg, estado en disco, reanudación y GUI nativa Tkinter.

**NO hemos conseguido aún** un video nuevo con la fidelidad visual de
`1000221974.mp4`. La calidad la dará el modelo ComfyUI real, sus nodos,
sus referencias y la evaluación de resultados. Las pruebas con modelos
simulados comprueban el cableado, no la estética. La narración Piper es opcional y utiliza el motor de voz original; no
ofrece voces dramatizadas por personaje, lipsync ni una métrica fiable de
identidad facial. No afirmar que estas partes están listas.

## Configuración de modelos (una vez)

Usa ComfyUI instalado localmente con los modelos descargados para:
- **character**: un modelo de imagen capaz de producir una **referencia
  maestra** desde texto. Solo necesario si faltan fotos de referencia.
- **keyframe**: un modelo de imagen que **acepte las referencias de identidad**
  y produzca una única imagen inicial de cada plano.
- **video**: modelo imagen-a-video que acepte la imagen inicial y produzca
  **un video MP4 u otro contenedor admitido**. Para 2D anime de alta calidad
  puedes evaluar workflows Wan2.2 I2V, controlando el uso de VRAM.

Exporta cada workflow en **formato API** desde ComfyUI. Un archivo visual
de la interfaz con nodo `nodes: [...]` no funciona. No hay IDs universales,
los bindings dependen de lo que exportes.

Copia `examples/studio_pro_v7/config.template.json` a otra carpeta,
renómbralo a `config.json` y reemplaza sus rutas por los JSON reales
exportados. Las rutas son relativas a la carpeta que contiene `config.json`.

Por ejemplo, bindings de keyframe (son **ejemplos de nombres**, no nodos
reales; deben apuntar a tu workflow API):

```json
{
  "positive_prompt": {"node": "6", "input": "text"},
  "negative_prompt": {"node": "7", "input": "text"},
  "reference_image": {"node": "12", "input": "image"}
}
```

Para dos personajes en un mismo plano, el workflow debe admitir otro
nodo de referencia y el binding `reference_image_2` o el proceso
**se detiene** en lugar de omitir silenciosamente a uno. Para la etapa
video, el binding `start_frame` o `reference_image` es obligatorio.

**La consistencia de personajes no está garantizada por los prompts.**
Solo un modelo con condicionamiento de referencia puede sostenerla y
el resultado visual debe comprobarse.

## Cómo ejecutar (un solo comando)

Desde la raíz del repositorio:

```powershell
python -m studio_pro gui
```

En la interfaz: selecciona config JSON, opcionalmente reparto,
pega la historia, elige carpeta y pulsa **GENERAR EPISODIO MP4**.
No hay que editar entre escenas, si las tres etapas/modelos funcionan.
El programa mostrará errores y conservará progreso por plano.

O desde CLI:

```powershell
# Solo validación: no arranca modelos
python -m studio_pro produce --script examples/production_story.txt --cast examples/production_cast.json --config config.json --out salida_pro/episodio

# Renderización real: solo después de instalar los modelos
python -m studio_pro produce --script examples/production_story.txt --cast examples/production_cast.json --config config.json --out salida_pro/episodio --execute --resume
```

Si un plano falla, el estado persiste en
`salida_pro/episodio/production_state.json`. Repite con `--resume`
y el programa no re-renderizará los planos terminados. **La configuración
y el libreto deben seguir siendo idénticos** para reanudar.

Salida esperada al completar:
- `production_plan.json`: despiece y referencias
- `references/`: personajes generados, cuando sean necesarios
- `shots/shot_XXX/keyframe/`: imagen inicial y workflow
- `shots/shot_XXX/motion/`: video y workflow
- `shots/shot_XXX/quality_report.json`
- `production_state.json`: estado real por escena
- `episodio.mp4`: solo cuando todos los videos están presentes

## Dependencias y limitaciones

- Python y FFmpeg disponibles, como ya exige el proyecto original.
- ComfyUI accesible en `http://127.0.0.1:8188`, modelos instalados.
- Los modelos de video de calidad suelen necesitar GPU potente; con un
  PC modesto se debe utilizar una GPU remota con túnel local seguro, o
  un servicio compatible. **No enviamos datos a un endpoint remoto directo.**
- Los flujos que usan servicios comerciales pueden consumir créditos: el
  botón exige confirmación antes de ejecutar.
- El análisis técnico de video detecta clips vacíos, casi estáticos o con
  proporciones equivocadas. No califica belleza, anatomía ni continuidad
  facial. En modo `strict_quality=true` interrumpe si detecta esos fallos.

## Referencias técnicas oficiales

- https://github.com/Comfy-Org/ComfyUI
- https://github.com/Comfy-Org/workflow_templates
- https://huggingface.co/Comfy-Org/Wan-2.2

## Antes de incorporar a main

La PR debe superar las pruebas unitarias y de integración, completar un
video con ComfyUI real, mantener identidad verificable entre planos, pasar
la revisión visual comparativa, y conservar el motor original tal como
estaba. Sin demostrarlo, no se fusiona.

## Narración y sonido (opcional)

El campo `voice` del config permite activar la voz Piper original de
Stickman IA:

```json
"voice": { "engine": "piper", "language": "es", "rate": 1.0 }
```

Una vez generado el video de cada escena, Piper sintetiza la narración y
FFmpeg la agrega sin sustituir los gráficos. Si el clip tiene sonido,
se reduce su volumen para escuchar la voz. El audio se conserva hasta
el archivo MP4 final. Si el audio dura más que el plano, se detiene con
un error claro **en lugar de cortar frases**; debes dividir la narración
o configurar un workflow que genere más segundos. La voz puede descargar
modelos gratuitos Piper si no están instalados, y depende de las
dependencias Python originales del proyecto.

`engine: "off"` mantiene el video sin narrador adicional.
