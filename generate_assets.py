import os
from PIL import Image

def generate_all_assets(source_path="logo.png"):
    if not os.path.exists(source_path):
        print(f"Error: {source_path} no encontrado.")
        return

    print(f"Cargando {source_path}...")
    img = Image.open(source_path).convert("RGBA")
    w, h = img.size
    max_dim = max(w, h)

    # Crear imagen cuadrada centrada con fondo transparente
    square_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
    offset_x = (max_dim - w) // 2
    offset_y = (max_dim - h) // 2
    square_img.paste(img, (offset_x, offset_y))

    os.makedirs("assets/icons", exist_ok=True)
    square_img.save("assets/logo_square.png")
    print("-> Guardado assets/logo_square.png")

    # Tamaños de iconos estándar para Android, Linux y Web
    sizes = [16, 24, 32, 48, 64, 128, 192, 256, 512]
    for s in sizes:
        resized = square_img.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(f"assets/icons/icon_{s}x{s}.png")
    print(f"-> Generados {len(sizes)} iconos PNG en assets/icons/")

    # Generar archivo .ICO multi-capa para Windows
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    square_img.save("assets/dxdesk.ico", format="ICO", sizes=ico_sizes)
    print("-> Guardado assets/dxdesk.ico (Windows)")

    # Generar archivo .ICNS para macOS
    try:
        square_img.save("assets/dxdesk.icns", format="ICNS")
        print("-> Guardado assets/dxdesk.icns (macOS)")
    except Exception as e:
        print(f"Aviso al generar ICNS: {e}")

if __name__ == "__main__":
    generate_all_assets()
