import flet as ft
import urllib.parse
import urllib.request
import json
from pathlib import Path
import webbrowser
from typing import Optional
from dataclasses import dataclass

@dataclass
class Chipa:
    id: Optional[int]
    nombre: str
    variante: str
    descripcion: str
    precio_base: float
    margen: float = 0.3
    disponible: bool = True
    ingredientes: Optional[str] = None

    def precio_final(self) -> float:
        return round(self.precio_base, 2)

# Datos locales
chipas = [
    Chipa(id=1, nombre="Chipá Tradicional", variante="Clásica", descripcion="Chipa con receta original Emboscada con queso, y fecula", precio_base=2000),
    Chipa(id=2, nombre="Chipá con Queso", variante="Extra Queso", descripcion="Chipa con receta original Emboscada con extra de queso cremos, y fecula", precio_base=2200),
    Chipa(id=3, nombre="Chipá con Salame", variante="Regional", descripcion="Chipa con receta original Emboscada con fiambre a elección(salame o paleta), y fecula", precio_base=2200),
]

# Número de WhatsApp receptor en formato internacional (sin +).
# Ejemplo Argentina: 54911xxxxxxx (54 código país, 9 para móvil cuando corresponde, 11 código de área)
# Cambiá este valor por el número al que quieras enviar los pedidos.
WHATSAPP_NUMBER = "5493456267933"
REMOTE_JSON_URL = "https://raw.githubusercontent.com/MauroAntonioBogado1990/preciosChipas/main/precios.json"  # reemplazá por tu URL raw

def main(page: ft.Page):
    page.title = "Simulador de Chipás Artesanales 🧀"
    page.scroll = "manual"

    # Construir UI: título, lista de chipas con contador, y formulario de pedido
    titulo = ft.Text("Elige tus chipas", size=28, weight="bold")

    # Contenedores para cada chipa: nombre, precio y contador
    filas_chipas = []
    # Guardar contadores por chipa
    contadores = {}

    def crear_fila_chipa(chipa: Chipa):
        contador = ft.TextField(value="0", width=70)
        contadores[chipa.id] = contador

        def incrementar(e):
            try:
                v = int(contador.value or "0") + 1
            except ValueError:
                v = 1
            contador.value = str(v)
            actualizar_total(None)
            page.update()

        def decrementar(e):
            try:
                v = max(0, int(contador.value or "0") - 1)
            except ValueError:
                v = 0
            contador.value = str(v)
            actualizar_total(None)
            page.update()

        fila = ft.Row([
            ft.Text(chipa.nombre, expand=True),
            ft.Text(chipa.descripcion, expand=True),
            ft.Text(f"${chipa.precio_base}"),
            ft.IconButton(ft.Icons.REMOVE, on_click=decrementar),
            contador,
            ft.IconButton(ft.Icons.ADD, on_click=incrementar),
        ], alignment="center")
        return fila

    for c in chipas:
        filas_chipas.append(crear_fila_chipa(c))

    # Formulario inferior: cliente, total y modo de pago
    campo_cliente = ft.TextField(label="Nombre de cliente", width=400)
    campo_total = ft.Text("Total: $0", weight="bold")
    modo_pago = ft.Dropdown(label="Modo de pago", width=200, options=[
        ft.dropdown.Option("Efectivo"),
        ft.dropdown.Option("Tarjeta"),
        ft.dropdown.Option("MercadoPago")
    ])

    def actualizar_total(e):
        total = 0
        for ch in chipas:
            try:
                qty = int(contadores[ch.id].value or "0")
            except Exception:
                qty = 0
            total += qty * ch.precio_final()
        campo_total.value = f"Total: ${total}"

    def fetch_remote_prices(url: str, timeout: int = 6) -> dict | None:
        try:
            print(f"[fetch_remote_prices] intentando {url}")
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                status = getattr(resp, 'status', None)
                print(f"[fetch_remote_prices] status={status}")
                if status is not None and status != 200:
                    print("[fetch_remote_prices] status != 200")
                    return None
                data = resp.read().decode("utf-8")
                obj = json.loads(data)
                if "chipas" not in obj or not isinstance(obj["chipas"], list):
                    print("[fetch_remote_prices] formato inesperado")
                    return None
                # cache local
                try:
                    Path("storage/data").mkdir(parents=True, exist_ok=True)
                    Path("storage/data/precios.json").write_text(data, encoding="utf-8")
                except Exception as e:
                    print(f"[fetch_remote_prices] no pudo escribir cache: {e}")
                print("[fetch_remote_prices] OK, retornando obj")
                return obj
        except Exception as exc:
            print(f"[fetch_remote_prices] excepción: {exc}")
            # intentar cache local
            try:
                cache_path = Path("storage/data/precios.json")
                if cache_path.exists():
                    cache_text = cache_path.read_text(encoding="utf-8")
                    print("[fetch_remote_prices] usando cache local")
                    return json.loads(cache_text)
            except Exception as e2:
                print(f"[fetch_remote_prices] no pudo leer cache: {e2}")
            return None

    def agregar_pedido(e):
        # Mostrar estado y luego intentar actualizar precios desde el repo
        page.snack_bar = ft.SnackBar(ft.Text(f"Intentando descargar precios de {REMOTE_JSON_URL}"))
        page.snack_bar.open = True
        page.update()
        remote = fetch_remote_prices(REMOTE_JSON_URL)
        print(f"[agregar_pedido] remote={bool(remote)}")
        if remote:
            # actualizar precios en memoria según id o nombre
            for r in remote.get("chipas", []):
                for ch in chipas:
                    if ("id" in r and r.get("id") == ch.id) or r.get("nombre") == ch.nombre:
                        try:
                            ch.precio_base = float(r.get("precio_base", ch.precio_base))
                        except Exception:
                            pass
        else:
            page.snack_bar = ft.SnackBar(ft.Text("No se pudo obtener precios remotos, usando valores locales/caché."))
            page.snack_bar.open = True
            page.update()

        # Recalcular detalle y total con precios actualizados
        nombre = campo_cliente.value or "(sin nombre)"
        pago = modo_pago.value or "(sin modo)"
        total = 0
        detalle_items = []
        for ch in chipas:
            try:
                qty = int(contadores[ch.id].value or "0")
            except Exception:
                qty = 0
            if qty > 0:
                subtotal = qty * ch.precio_final()
                detalle_items.append((qty, ch.nombre, ch.precio_base, subtotal))
            total += qty * ch.precio_final()

        # Construir contenido del diálogo resumen
        if not detalle_items:
            page.snack_bar = ft.SnackBar(ft.Text("No hay items en el pedido."))
            page.snack_bar.open = True
            page.update()
            return

        # Diagnostic: mostrar en snack y en consola el número de items y total
        page.snack_bar = ft.SnackBar(ft.Text(f"Items: {len(detalle_items)} - Total: ${total}"))
        page.snack_bar.open = True
        page.update()
        print(f"[agregar_pedido] detalle_items={detalle_items} total={total}")

        contenido = [ft.Text(f"Cliente: {nombre}"), ft.Text(f"Modo de pago: {pago}"), ft.Divider()]
        for qty, nombre_item, precio_unit, subtotal in detalle_items:
            contenido.append(ft.Text(f"{qty} x {nombre_item} @ ${precio_unit} = ${subtotal}"))
        contenido.append(ft.Divider())
        contenido.append(ft.Text(f"Total: ${total}", weight="bold"))

        # Mostrar resumen inline y habilitar botón confirmar
        resumen.controls = contenido
        boton_confirmar.visible = True

        # handler que enviará el pedido por WhatsApp
        def enviar_confirm(e):
            detalle_text = ", ".join([f"{q} x {n}" for q, n, _, _ in detalle_items])
            mensaje = f"Pedido de {nombre}: {detalle_text} - Total: ${total} - Pago: {pago}"
            try:
                text = mensaje
                encoded = urllib.parse.quote_plus(text)
                url = f"https://api.whatsapp.com/send?phone={WHATSAPP_NUMBER}&text={encoded}"
                try:
                    ft.launch_url(url)
                except Exception:
                    webbrowser.open(url)
                page.snack_bar = ft.SnackBar(ft.Text("Enviando pedido..."))
                page.snack_bar.open = True
            except Exception as exc:
                page.snack_bar = ft.SnackBar(ft.Text(f"No se pudo enviar: {exc}"))
                page.snack_bar.open = True
            # Reset y ocultar resumen + boton
            for ctrl in contadores.values():
                ctrl.value = "0"
            actualizar_total(None)
            boton_confirmar.visible = False
            resumen.controls = []
            page.update()

        boton_confirmar.on_click = enviar_confirm
        page.update()

    boton_agregar = ft.ElevatedButton(text="Pedir", on_click=agregar_pedido)

    # Resumen y botón confirmar (inicialmente oculto)
    resumen = ft.Column()
    boton_confirmar = ft.ElevatedButton(text="Confirmar pedido", on_click=None, visible=False)

    # Layout principal
    page.add(
        titulo,
        ft.Column(filas_chipas),
        ft.Divider(),
        campo_cliente,
        ft.Row([campo_total, modo_pago, boton_agregar, boton_confirmar], alignment="spaceBetween"),
        resumen
    )

if __name__ == "__main__":
    ft.app(target=main)