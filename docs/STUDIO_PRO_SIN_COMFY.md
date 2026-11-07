# Studio Pro: generar MP4 usando el motor original

Esta ruta **NO** usa Higgsfield, ComfyUI ni APIs de pago.

## Ruta de Windows

1. Extrae/descarga la rama `feat/studio-pro-motor-original-sin-comfy-v8`.
2. Ejecuta una vez `INSTALAR_MOTOR_STICKMAN_LOCAL.bat`.
3. Abre `ABRIR_STUDIO_PRO.bat`.
4. Marca **Motor original Stickman IA 2D — sin configuración**.
5. Pulsa **Cargar historia zombi**, luego **1. VALIDAR GUIÓN**.
6. Pulsa **2. GENERAR EPISODIO MP4** y comprueba el registro en tiempo real.
7. Haz clic en **Abrir carpeta**. El archivo es `episodio_stickman.mp4`.

La primera ejecución puede descargar gratis la voz Piper al directorio
de caché. Instala FFmpeg y añade su ejecutable al PATH de Windows.

## Por consola
```powershell
.\.venv\Scripts\python.exe -m studio_pro original --script examples/la_vecina/historia.txt --cast examples/la_vecina/personajes.json --out salida/la_vecina --execute
```

Para validar sin generar audio/video, omite `--execute`.

## Qué se produce y qué no

Se usa el renderizador original de Stickman IA: personajes vectoriales,
poses, desplazamientos, camera, fondos y lluvia opcional, Piper local,
subtítulos y MP4. Es una **animación auténtica del repositorio**.

El adaptador de libreto libre funciona con reglas deterministas
limitadas; no comprende el texto tan bien como un LLM. También faltan
actuaciones complejas como una caída de cabeza o la física de volteretas,
y los objetos televisión, nevera y cercas todavía no están modelados
con todo el detalle solicitado. No es un modelo anime avanzado.

El modo neuronal Pro continúa disponible, separado y experimental,
pero necesita modelos reales. No se sustituye ni se elimina el original.
