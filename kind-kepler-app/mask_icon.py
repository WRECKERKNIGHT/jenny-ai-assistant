import os
import sys
from PIL import Image, ImageDraw

def mask_logo(input_path, output_path):
    print(f"Masking {input_path} to macOS squircle design...")
    # Open original image and convert to RGBA
    img = Image.open(input_path).convert("RGBA")

    # Resize to standard high-res macOS app icon size: 1024x1024
    img = img.resize((1024, 1024), Image.Resampling.LANCZOS)

    # Create transparent mask
    mask = Image.new("L", (1024, 1024), 0)
    draw = ImageDraw.Draw(mask)

    # Modern macOS squircle bounding box inside 1024x1024 image.
    # The generated squircle starts around 145px from edges.
    left, top = 145, 145
    right, bottom = 879, 879
    radius = 162

    # Draw rounded rect mask
    draw.rounded_rectangle(
        [left, top, right, bottom],
        radius=radius,
        fill=255
    )

    # Apply mask to image
    output = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask=mask)

    # Save as PNG
    output.save(output_path, "PNG")
    print("Successfully masked and saved logo with transparent corners.")
    return output_path

def generate_sizes(icon_path, out_dir):
    """Emit 192/512 PWA icons from the masked 1024 source."""
    os.makedirs(out_dir, exist_ok=True)
    img = Image.open(icon_path).convert("RGBA")
    for size in (192, 512):
        path = os.path.join(out_dir, f"icon-{size}x{size}.png")
        img.resize((size, size), Image.Resampling.LANCZOS).save(path, "PNG")
        print(f"Generated {path}")

if __name__ == "__main__":
    args = sys.argv[1:]
    inp = args[0] if args and not args[0].startswith("--") else "logo.png"
    outp = args[1] if len(args) > 1 and not args[1].startswith("--") else "logo.png"
    masked = mask_logo(inp, outp)
    if "--pwa" in args:
        generate_sizes(masked, "icons")