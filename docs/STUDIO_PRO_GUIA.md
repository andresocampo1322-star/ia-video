# Studio Pro experimental: libreto -> plan audiovisual -> motor generativo opcional

**Objetivo visual de referencia:** animación anime/manga de alta definición,
composición vertical 9:16, personajes reconocibles entre planos, vestuario estable,
escenarios detallados en perspectiva, tonos grises matizados, sombras suaves y
montaje coherente. Este objetivo procede del video aportado como referencia para
el proyecto; el video no se incorpora al repositorio.

## Política de compatibilidad

- `python -m stickman` y el pipeline de Skia/Piper/FFmpeg **no se alteran**.
- La ruta avanzada se ejecuta por separado con `python -m studio_pro`.
- En la rama principal no se incorpora nada sin pruebas y evaluación visual.
- Ninguna opción llamada "manga", "anime" o "3D" equivale a un render real:
  el estilo se vuelve gráfico solo cuando lo interpreta el motor generativo.
- Una referencia de personaje debe existir y mantener consistencia; una semilla
  estable por sí sola NO garantiza identidad visual.

## 1. Planificar un libreto con Python estándar

Desde la carpeta raíz del proyecto (Python 3.12 o compatible):

```powershell
python -m studio_pro skills
python -m studio_pro plan --script examples/production_story.txt --cast examples/production_cast.json --style manga_monochrome --format 9:16 --out salida_pro
```

Genera `salida_pro/production_plan.json` y
`shot_001_prompt.txt`, `shot_002_prompt.txt`, etc. No usa TTS, GPU ni
servicio web. El planificador sin LLM es deliberadamente **heurístico**:
separa párrafos, detecta localizaciones y propone encuadres sencillos.
NO interpreta semántica compleja con fiabilidad humana.

### Personajes diversos y permanentes

Edita `examples/production_cast.json`, asignando a cada personaje:

- `name`, `appearance` (rostro, cabello, edad aproximada, complexión);
- `clothing`, `distinctive_features` (vestuario y marcas distintivas);
- `reference_image`: nombre o ruta de una imagen maestra propia.
- El mismo identificador y diseño se repiten en todos los prompts.

Para mantener el aspecto entre escenas, el motor generativo elegido debe
**admitir y utilizar esa referencia**; no basta con escribir el mismo prompt.
Las hojas de modelo multiángulo y su generación automática están pendientes.

## 2. Mejor interpretación del texto: Ollama local (opcional)

```powershell
python -m studio_pro plan --script examples/production_story.txt --style manga_monochrome --ollama-model TU_MODELO_OLLAMA --out salida_pro_ollama
```

Requiere instalar Ollama y descargar un modelo de texto compatible. No
hay llamadas de red salvo al servicio local `127.0.0.1:11434`.
El analizador pide reparto, localizaciones, acciones y división por planos,
validando su salida JSON. Si Ollama no está instalado, la app comunica
el error; no inventa un resultado de modelo.

Revisa siempre las sugerencias del LLM: puede omitir o inventar información.
Si la fidelidad al libreto importa, edita el plan resultante.

## 3. Motor generativo: ComfyUI (opcional, requiere hardware/modelos)

Para una calidad comparable al video de referencia, un motor vectorial simple
no basta. Una vía real consiste en generar referencias/primeros fotogramas
detallados con un modelo de imagen, animarlos en modelos de video que admitan
imagen-a-video y montar los planos en un episodio.

- `studio_pro/comfy.py` acepta **workflow API JSON real** exportado desde ComfyUI.
- `bindings.json` asigna parámetros semánticos a `node` e `input` reales.
- El modo predeterminado SOLO prepara JSON por plano (no consume recursos).
- `--submit` envía los flujos a ComfyUI local.
- `--wait` consulta la ejecución y descarga los archivos reportados.
- Los resultados **dependen del workflow**, sus modelos, sus nodos y referencias.

Ejemplo de contrato, no IDs universales:

```json
{
  "positive_prompt": {"node": "6", "input": "text"},
  "negative_prompt": {"node": "7", "input": "text"},
  "seed": {"node": "3", "input": "seed"},
  "width": {"node": "5", "input": "width"},
  "height": {"node": "5", "input": "height"},
  "frames": {"node": "5", "input": "length"}
}
```

**Sustituye esos IDs y nombres por los de tu workflow exportado en formato API.**
No existe un único workflow válido para todos los modelos.

```powershell
# Preparar flujos sin generar ni gastar créditos:
python -m studio_pro render-project --project salida_pro/production_plan.json --workflow MI_WORKFLOW_API.json --bindings MIS_BINDINGS.json --out salida_pro/workflows

# Solo con ComfyUI configurado y modelo compatible:
python -m studio_pro render-project --project salida_pro/production_plan.json --workflow MI_WORKFLOW_API.json --bindings MIS_BINDINGS.json --out salida_pro/renders --submit --wait
```

Algunos flujos pueden utilizar nodos comerciales que **sí cobran**.
El parámetro `--submit` tiene que ser una elección deliberada.

Si el workflow exige una imagen de referencia, primero hay que importarla
al directorio de entrada de ComfyUI y asignar su parámetro correspondiente;
la infraestructura actual no crea automáticamente hojas de personaje.
Para varios personajes por plano se requiere workflow de múltiples referencias.

## 4. Qué skills existen y qué falta

`python -m studio_pro skills` devuelve el contrato de cada skill, su
dependencia y si está implementada, limitada o pendiente.

**Disponibles ahora (con alcance limitado cuando corresponda):**
lectura de libreto; biblia de personajes proporcionada o inferida;
plan de escenas; perfiles de estilo; composición de prompts y exportación;
vinculación de workflows API; envío y recuperación desde ComfyUI local.

**Pendientes:** generación de hojas de personaje coherentes multiángulo,
evaluación automática de identidad, control del movimiento y eliminación de
parpadeos, lipsync semántico, montaje automático con audio para un episodio
completo y una interfaz visual unificada.

Por tanto, **este avance NO equivale a generar automáticamente desde texto
el video completo de referencia**. Es el cimiento funcional de esa ruta.

## 5. Requerimientos reales del motor generativo

Según la documentación de LTX-2.5, una configuración local de referencia
requiere una GPU NVIDIA de **32 GB de VRAM o más**, 32 GB RAM y 100 GB de
almacenamiento, aunque pueden existir variantes cuantizadas y servicios
remotos. No recomendamos instalar modelos gigantes en un equipo modesto.

Fuentes oficiales:
- https://docs.ltx.io/open-source-model/getting-started/system-requirements
- https://docs.ltx.io/open-source-model/integration-tools/comfy-ui
- https://docs.ltx.io/models/ltx-2-5
- https://huggingface.co/Comfy-Org/Wan-2.2

Para democratizar el uso deben contemplarse GPU remota, presupuesto,
permisos de derechos de contenido, caché de clips, reintentos y
preservación de referencias entre episodios.

## 6. Criterios de aceptación del nivel de referencia

1. Mismo rostro, peinado, ropa, altura y silueta en todos los planos.
2. Movimiento temporal real, sin simples transiciones de diapositivas.
3. Escenarios con perspectiva, mobiliario, reflejos y escala estable.
4. Continuidad narrativa: ubicación, dirección de mirada y objetos.
5. Edición por planos y sonido sincronizado.
6. Pruebas con libreto nuevo no utilizado para diseñar las reglas.
7. Comparación de resultados reales antes de considerar una skill terminada.

La prioridad no es llenar una lista de botones; es comprobar que cada
componente aumenta la calidad visible y mantiene la compatibilidad.
