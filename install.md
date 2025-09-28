# Guía de instalación y uso con Docker y Claude Desktop (MCP)

Este documento explica cómo construir la imagen Docker del servidor MCP de acciones (yfinance-mcp-server), cargarlo a través de un Docker MCP gateway y probar sus herramientas desde Claude Desktop. Todo sin exponer puertos, usando stdio como transporte MCP.

Índice:
- Requisitos
- Construir la imagen Docker
- Prueba rápida local (opcional)
- Opción A: Integrar mediante Docker MCP gateway (recomendado)
- Opción B: Integrar llamando `docker run` directamente desde Claude Desktop
- Probar las herramientas desde Claude
- Solución de problemas

## Requisitos
- Docker instalado y funcionando (capaz de construir imágenes).
- Conexión a Internet en tiempo de ejecución (el servidor usa yfinance para consultar Yahoo Finance).
- Claude Desktop instalado (versión con soporte para MCP Servers).
- Opcional (para Opción A): tener instalado el Docker MCP gateway en tu sistema. Si no lo tienes, puedes usar la Opción B.

Notas del proyecto:
- Runtime: Python 3.13 (dentro de la imagen Docker).
- Entrada principal: `stock_price_server.py` (servidor MCP vía stdio).
- Nombre del servidor MCP: "Stock Price Server".

## Construir la imagen Docker
En la raíz del repo:

```bash
docker build -t yfinance-mcp-server .
```

Esto crea una imagen con el entrypoint adecuado (`python3 stock_price_server.py`) que expone el servidor MCP por stdio.

## Prueba rápida local (opcional)
Puedes probar que el contenedor inicia correctamente (se quedará a la espera por stdio; usa Ctrl+C para salir):

```bash
docker run --rm yfinance-mcp-server
```

Si no ves salida, es normal: el servidor MCP espera que un cliente MCP se conecte por stdin/stdout.

## Opción A: Integración mediante Docker MCP gateway (recomendado)
La idea es que Claude Desktop ejecute el gateway, y éste arranque el contenedor Docker y proxyee stdio.

1) Instalar el gateway (si aún no lo tienes). Existen distintas distribuciones; instala según la documentación de tu gateway Docker MCP preferido. Un binario habitual expone el comando `mcp-docker-gateway`.

2) Configurar Claude Desktop para usar el gateway con esta imagen:
   - Abre Claude Desktop → Settings → MCP Servers → Add new server.
   - Tipo: Command (stdio).
   - Command: `mcp-docker-gateway`
   - Arguments: `--image yfinance-mcp-server`
   - (Opcional) Más argumentos del gateway si los necesitas (p. ej., variables de entorno, flags de Docker). Por defecto, el Dockerfile ya lleva el `CMD ["python3","stock_price_server.py"]`.

Con esto, cuando Claude inicie el servidor, el gateway levantará `docker run -i --rm yfinance-mcp-server` y conectará stdio al cliente MCP.

Notas:
- Si tu gateway admite especificar un comando distinto al `CMD` de la imagen, puedes añadirlo, pero no es necesario para este proyecto.
- Si tu gateway requiere configuración por archivo JSON/YAML, define algo equivalente a: command `mcp-docker-gateway` con args `--image yfinance-mcp-server`.

## Opción B: Integración llamando `docker run` directamente desde Claude Desktop
Si no quieres instalar un gateway extra, puedes pedirle a Claude que ejecute Docker directamente como comando MCP stdio.

1) En Claude Desktop → Settings → MCP Servers → Add new server.
2) Tipo: Command (stdio).
3) Command: `docker`
4) Arguments: `run -i --rm yfinance-mcp-server`

Claude ejecutará ese proceso y conectará stdio; como el servidor dentro del contenedor ya corre por stdio, funcionará igual que con el gateway.

Sugerencias:
- En Linux, puede que necesites permisos para ejecutar Docker como tu usuario (o usar `sudo`). Claude Desktop normalmente no puede pedir password de sudo; en ese caso, usa la Opción A (gateway) o agrega tu usuario al grupo `docker`.

## Probar las herramientas desde Claude
Una vez agregado el servidor, abre un chat y verifica que Claude detecta el servidor "Stock Price Server" y sus herramientas. Puedes:

- Pedir: "Muestra la lista de herramientas del servidor de acciones".
- O invocar la herramienta de lista explícitamente si tu cliente lo permite: `list_tools`.

Resultados esperados de `list_tools()` incluyen entradas como:
- `get_stock_price(symbol: str) -> float`
- `get_stock_history(symbol: str, period: str = "1mo") -> str`
- `compare_stocks(symbol1: str, symbol2: str) -> str`
- `list_stock_symbols(query: str, limit: int = 10) -> list[str]`

Ejemplos de uso típicos en conversación:
- "Dime el precio actual de AAPL usando el servidor MCP de acciones."
- "Compara AAPL y MSFT."
- "Lista símbolos que coincidan con 'micro' (limite 5)."

Notas sobre red y datos:
- `get_stock_price` y `get_stock_history` requieren Internet para consultar Yahoo Finance.
- `list_stock_symbols` también consulta Yahoo. Si no hay red, obtendrás resultados vacíos o valores de fallback.

## Solución de problemas
- El servidor no aparece en Claude:
  - Verifica que la imagen existe: `docker images | grep yfinance-mcp-server`.
  - En Opción A: confirma que `mcp-docker-gateway` está instalado y en tu `PATH`.
  - En Opción B: asegúrate de que `docker` puede ejecutarse sin sudo desde Claude Desktop.
- El contenedor se cierra inmediatamente:
  - Asegúrate de no pasar comandos extra que sustituyan el `CMD` del Dockerfile.
- Sin Internet desde el contenedor:
  - Revisa la conectividad del host y políticas de red corporativas. El contenedor no abre puertos; solo hace salidas HTTP(S).
- Logs:
  - El servidor escribe logs dentro del contenedor en `logs/YYYY-MM-DD.log`. Para inspeccionarlos en ejecución, usa otra terminal y `docker ps` + `docker logs <container>` (si tu plataforma lo permite) o monta un volumen si necesitas persistir `./logs`.

## Resumen
- Construye la imagen: `docker build -t yfinance-mcp-server .`
- Integra con Claude:
  - Opción A (gateway): Command `mcp-docker-gateway`, Args `--image yfinance-mcp-server`.
  - Opción B (directo): Command `docker`, Args `run -i --rm yfinance-mcp-server`.
- Prueba `list_tools` y las demás herramientas desde Claude Desktop.
